#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas",
#     "plotly",
# ]
# ///

import argparse
import sqlite3
import sys
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def main():
    parser = argparse.ArgumentParser(description="Visualize data holes in radio station scraper database.")
    parser.add_argument("db_path", type=str, help="Path to the SQLite database file.")
    parser.add_argument("--station", type=str, nargs='+', 
                        help="Specific station name(s) to include (e.g., --station 'Radio 1' 'Radio 2').")
    parser.add_argument("--gap-threshold", type=float, default=3.0, 
                        help="Minimum gap in hours to be considered a 'hole' (default: 3.0).")
    parser.add_argument("--viz-type", choices=['gantt', 'line', 'heatmap'], default='gantt',
                        help="Type of visualization to generate (default: gantt).")
    parser.add_argument("--all-stations", action="store_true", 
                        help="Include all stations (by default, only enabled=1 stations are included).")
    parser.add_argument("--output", type=str, default="station_gaps.html", 
                        help="Output HTML file path (default: station_gaps.html).")
    
    args = parser.parse_args()
    db_file = Path(args.db_path)

    if not db_file.exists():
        print(f"Error: Database file '{args.db_path}' not found.")
        sys.exit(1)

    # Determine station filter and SQL parameters to prevent injection
    query_params = ()
    if args.station:
        placeholders = ', '.join(['?'] * len(args.station))
        station_filter = f"s.name IN ({placeholders})"
        query_params = tuple(args.station)
    else:
        station_filter = "1=1" if args.all_stations else "s.enabled = 1"

    print(f"Connecting to {args.db_path} (Read-Only)...")
    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)

    print("Fetching earliest play dates for each station...")
    first_play_query = f"""
    SELECT 
        s.name AS station_name, 
        MIN(p.time) AS earliest_time
    FROM scraper_station s
    JOIN scraper_play p ON s.id = p.station_id
    WHERE {station_filter}
    GROUP BY s.name
    """
    first_play_df = pd.read_sql_query(first_play_query, conn, params=query_params)
    first_play_df['earliest_time'] = pd.to_datetime(first_play_df['earliest_time'])
    first_play_df['hover_time_str'] = first_play_df['earliest_time'].dt.strftime('%Y-%m-%d %H:%M:%S')

    print(f"Calculating total hours of silence (gaps >= {args.gap_threshold}h) per station...")
    # New query to calculate the cumulative total of the holes per station
    gap_summary_query = f"""
    WITH PlayTimes AS (
        SELECT 
            s.name AS station_name,
            p.time,
            LEAD(p.time) OVER (PARTITION BY p.station_id ORDER BY p.time) AS next_time
        FROM scraper_play p
        JOIN scraper_station s ON p.station_id = s.id
        WHERE {station_filter}
    )
    SELECT 
        station_name, 
        SUM((julianday(next_time) - julianday(time)) * 24) AS total_gap_hours
    FROM PlayTimes
    WHERE (julianday(next_time) - julianday(time)) * 24 >= ? AND next_time IS NOT NULL
    GROUP BY station_name
    """
    gap_summary_df = pd.read_sql_query(gap_summary_query, conn, params=query_params + (args.gap_threshold,))
    gap_dict = gap_summary_df.set_index('station_name')['total_gap_hours'].to_dict()

    # Function to append the total number of hours missing to the station name
    def format_station_label(name):
        gaps = gap_dict.get(name, 0.0)
        return f"{name} ({gaps:.1f}h missing)"

    # Apply the new labels to our first play dataframe
    first_play_df['station_name'] = first_play_df['station_name'].apply(format_station_label)

    if args.viz_type == 'gantt':
        print(f"Calculating exact gaps >= {args.gap_threshold} hours...")
        query = f"""
        WITH PlayTimes AS (
            SELECT 
                s.name AS station_name,
                p.time,
                LEAD(p.time) OVER (PARTITION BY p.station_id ORDER BY p.time) AS next_time
            FROM scraper_play p
            JOIN scraper_station s ON p.station_id = s.id
            WHERE {station_filter}
        )
        SELECT 
            station_name, 
            time AS start_time, 
            next_time AS end_time,
            (julianday(next_time) - julianday(time)) * 24 AS gap_hours
        FROM PlayTimes
        WHERE gap_hours >= ? AND next_time IS NOT NULL
        """
        df = pd.read_sql_query(query, conn, params=query_params + (args.gap_threshold,))
        
        if df.empty:
            print(f"No gaps found larger than {args.gap_threshold} hours.")
            sys.exit(0)

        df['start_time'] = pd.to_datetime(df['start_time'])
        df['end_time'] = pd.to_datetime(df['end_time'])
        # Apply the new station labels
        df['station_name'] = df['station_name'].apply(format_station_label)
        
        print("Generating Gantt chart...")
        fig = px.timeline(
            df, x_start="start_time", x_end="end_time", y="station_name", 
            color="gap_hours", hover_data=["gap_hours"],
            title=f"Scraper Data Holes (Gaps > {args.gap_threshold} Hours)",
            labels={"station_name": "Station", "gap_hours": "Gap Duration (Hours)"},
            color_continuous_scale="Reds"
        )
        fig.update_yaxes(autorange="reversed")

        # Overlay the bright green line with explicit hover text
        fig.add_trace(go.Scatter(
            x=first_play_df['earliest_time'],
            y=first_play_df['station_name'],
            mode='markers',
            marker=dict(color='#00FF00', size=14, symbol='line-ns', line=dict(width=4, color='#00FF00')),
            name='Earliest Play',
            customdata=first_play_df['hover_time_str'],
            hovertemplate="<b>%{y}</b><br>First Play: %{customdata}<extra></extra>"
        ))

    else:
        print("Aggregating daily play counts...")
        query = f"""
        SELECT 
            s.name AS station_name,
            date(p.time) AS play_date,
            COUNT(p.id) AS play_count
        FROM scraper_station s
        LEFT JOIN scraper_play p ON s.id = p.station_id
        WHERE {station_filter}
        GROUP BY s.name, play_date
        HAVING play_date IS NOT NULL
        """
        df = pd.read_sql_query(query, conn, params=query_params)
        
        if df.empty:
            print("No data found to plot.")
            sys.exit(0)

        df['play_date'] = pd.to_datetime(df['play_date'])
        # Apply the new station labels
        df['station_name'] = df['station_name'].apply(format_station_label)
        
        all_dates = pd.date_range(start=df['play_date'].min(), end=df['play_date'].max())
        stations = df['station_name'].unique()
        idx = pd.MultiIndex.from_product([stations, all_dates], names=['station_name', 'play_date'])
        
        df = df.set_index(['station_name', 'play_date']).reindex(idx, fill_value=0).reset_index()

        first_play_df['earliest_date'] = first_play_df['earliest_time'].dt.normalize()

        if args.viz_type == 'line':
            print("Generating Line chart...")
            fig = px.line(
                df, x="play_date", y="play_count", color="station_name",
                title="Daily Play Counts per Station (Drops indicate holes)",
                labels={"play_date": "Date", "play_count": "Songs Scraped", "station_name": "Station"}
            )
            
            first_play_merged = pd.merge(first_play_df, df, on=['station_name', 'earliest_date'])
            
            fig.add_trace(go.Scatter(
                x=first_play_merged['earliest_date'], y=first_play_merged['play_count'],
                mode='markers', marker=dict(color='#00FF00', size=10, symbol='diamond'),
                name='Earliest Play',
                customdata=first_play_merged['hover_time_str'],
                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>First Play: %{customdata}<br>Play Count: %{y}<extra></extra>"
            ))
            
        elif args.viz_type == 'heatmap':
            print("Generating Heatmap...")
            pivot_df = df.pivot(index="station_name", columns="play_date", values="play_count")
            
            fig = px.imshow(
                pivot_df, title="Daily Play Counts Heatmap (Dark areas indicate holes)",
                labels=dict(x="Date", y="Station", color="Songs Scraped"),
                aspect="auto", color_continuous_scale="Viridis"
            )
            
            fig.add_trace(go.Scatter(
                x=first_play_df['earliest_date'], y=first_play_df['station_name'],
                mode='markers', marker=dict(color='#00FF00', size=14, symbol='line-ns', line=dict(width=4, color='#00FF00')),
                name='Earliest Play',
                customdata=first_play_df['hover_time_str'],
                hovertemplate="<b>%{y}</b><br>First Play: %{customdata}<extra></extra>"
            ))

    fig.write_html(args.output)
    print(f"Done! Visualization saved to: {args.output}")

if __name__ == "__main__":
    main()