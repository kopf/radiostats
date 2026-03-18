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
                        help="Minimum gap in hours to be considered a 'hole' (default: 3.0). Only applies to Gantt.")
    parser.add_argument("--all-stations", action="store_true", 
                        help="Include all stations (by default, only enabled=1 stations are included).")
    parser.add_argument("--output", type=str, default="station_gaps.html", 
                        help="Base output HTML file path. Graph types will be appended (e.g., station_gaps_gantt.html).")
    
    args = parser.parse_args()
    db_file = Path(args.db_path)

    if not db_file.exists():
        print(f"Error: Database file '{args.db_path}' not found.")
        sys.exit(1)

    # Parse output filename to inject graph types later
    out_path = Path(args.output)
    out_dir = out_path.parent
    out_stem = out_path.stem
    out_ext = out_path.suffix if out_path.suffix else ".html"

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

    # --- 1. Fetch metadata (Earliest plays and Cumulative gaps) ---
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
    
    if first_play_df.empty:
        print("No station data found matching your criteria. Exiting.")
        sys.exit(0)
        
    first_play_df['earliest_time'] = pd.to_datetime(first_play_df['earliest_time'])
    first_play_df['hover_time_str'] = first_play_df['earliest_time'].dt.strftime('%Y-%m-%d %H:%M:%S')

    print(f"Calculating total hours of silence (gaps >= {args.gap_threshold}h) per station...")
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

    def format_station_label(name):
        gaps = gap_dict.get(name, 0.0)
        return f"{name} ({gaps:.1f}h silence)"

    first_play_df['station_name'] = first_play_df['station_name'].apply(format_station_label)
    first_play_df['earliest_date'] = first_play_df['earliest_time'].dt.normalize()

    # --- 2. Fetch and Generate GANTT Chart ---
    print(f"\n[1/3] Fetching exact gaps for Gantt chart...")
    gantt_query = f"""
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
    gantt_df = pd.read_sql_query(gantt_query, conn, params=query_params + (args.gap_threshold,))
    
    if not gantt_df.empty:
        gantt_df['start_time'] = pd.to_datetime(gantt_df['start_time'])
        gantt_df['end_time'] = pd.to_datetime(gantt_df['end_time'])
        gantt_df['station_name'] = gantt_df['station_name'].apply(format_station_label)
        
        print("      Generating Gantt chart...")
        fig_gantt = px.timeline(
            gantt_df, x_start="start_time", x_end="end_time", y="station_name", 
            color="gap_hours", hover_data=["gap_hours"],
            title=f"Scraper Data Holes (Gaps > {args.gap_threshold} Hours)",
            labels={"station_name": "Station", "gap_hours": "Gap Duration (Hours)"},
            color_continuous_scale="Reds"
        )
        fig_gantt.update_yaxes(autorange="reversed")

        fig_gantt.add_trace(go.Scatter(
            x=first_play_df['earliest_time'], y=first_play_df['station_name'],
            mode='markers', marker=dict(color='#00FF00', size=14, symbol='line-ns', line=dict(width=4, color='#00FF00')),
            name='Earliest Play', customdata=first_play_df['hover_time_str'],
            hovertemplate="<b>%{y}</b><br>First Play: %{customdata}<extra></extra>"
        ))
        
        gantt_file = out_dir / f"{out_stem}_gantt{out_ext}"
        fig_gantt.write_html(gantt_file)
        print(f"      -> Saved {gantt_file}")
    else:
        print(f"      No gaps >= {args.gap_threshold}h found. Skipping Gantt chart.")

    # --- 3. Fetch Data for Line & Heatmap Charts ---
    print("\n[2/3 & 3/3] Fetching daily aggregations for Line and Heatmap charts...")
    daily_query = f"""
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
    daily_df = pd.read_sql_query(daily_query, conn, params=query_params)
    
    if not daily_df.empty:
        daily_df['play_date'] = pd.to_datetime(daily_df['play_date'])
        daily_df['station_name'] = daily_df['station_name'].apply(format_station_label)
        
        # Create continuous date grid
        all_dates = pd.date_range(start=daily_df['play_date'].min(), end=daily_df['play_date'].max())
        stations = daily_df['station_name'].unique()
        idx = pd.MultiIndex.from_product([stations, all_dates], names=['station_name', 'play_date'])
        daily_df = daily_df.set_index(['station_name', 'play_date']).reindex(idx, fill_value=0).reset_index()

        # --- Generate Line Chart ---
        print("      Generating Line chart...")
        fig_line = px.line(
            daily_df, x="play_date", y="play_count", color="station_name",
            title="Daily Play Counts per Station (Drops indicate holes)",
            labels={"play_date": "Date", "play_count": "Songs Scraped", "station_name": "Station"}
        )
        
        first_play_merged = pd.merge(first_play_df, daily_df, on=['station_name', 'earliest_date'])
        fig_line.add_trace(go.Scatter(
            x=first_play_merged['earliest_date'], y=first_play_merged['play_count'],
            mode='markers', marker=dict(color='#00FF00', size=10, symbol='diamond'),
            name='Earliest Play', customdata=first_play_merged['hover_time_str'],
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>First Play: %{customdata}<br>Play Count: %{y}<extra></extra>"
        ))
        
        line_file = out_dir / f"{out_stem}_line{out_ext}"
        fig_line.write_html(line_file)
        print(f"      -> Saved {line_file}")

        # --- Generate Heatmap ---
        print("      Generating Heatmap...")
        pivot_df = daily_df.pivot(index="station_name", columns="play_date", values="play_count")
        
        fig_heatmap = px.imshow(
            pivot_df, title="Daily Play Counts Heatmap (Dark areas indicate holes)",
            labels=dict(x="Date", y="Station", color="Songs Scraped"),
            aspect="auto", color_continuous_scale="Viridis"
        )
        
        fig_heatmap.add_trace(go.Scatter(
            x=first_play_df['earliest_date'], y=first_play_df['station_name'],
            mode='markers', marker=dict(color='#00FF00', size=14, symbol='line-ns', line=dict(width=4, color='#00FF00')),
            name='Earliest Play', customdata=first_play_df['hover_time_str'],
            hovertemplate="<b>%{y}</b><br>First Play: %{customdata}<extra></extra>"
        ))
        
        heatmap_file = out_dir / f"{out_stem}_heatmap{out_ext}"
        fig_heatmap.write_html(heatmap_file)
        print(f"      -> Saved {heatmap_file}")
    else:
        print("      No daily data found. Skipping Line and Heatmap charts.")

    print("\nDone! All available visualizations have been saved.")

if __name__ == "__main__":
    main()