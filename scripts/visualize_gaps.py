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

def main():
    parser = argparse.ArgumentParser(description="Visualize data holes in radio station scraper database.")
    parser.add_argument("db_path", type=str, help="Path to the SQLite database file.")
    parser.add_argument("--gap-threshold", type=float, default=3.0, 
                        help="Minimum gap in hours to be considered a 'hole' (default: 3.0). Only applies to Gantt.")
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

    # Determine station filter
    station_filter = "1=1" if args.all_stations else "s.enabled = 1"

    print(f"Connecting to {args.db_path}...")
    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)

    if args.viz_type == 'gantt':
        print(f"Calculating exact gaps >= {args.gap_threshold} hours...")
        # Use SQLite window functions to find gaps efficiently without loading all rows into RAM
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
        df = pd.read_sql_query(query, conn, params=(args.gap_threshold,))
        
        if df.empty:
            print(f"No gaps found larger than {args.gap_threshold} hours. Good job, scraper!")
            sys.exit(0)

        # Convert to datetime for Plotly
        df['start_time'] = pd.to_datetime(df['start_time'])
        df['end_time'] = pd.to_datetime(df['end_time'])
        
        print("Generating Gantt chart...")
        fig = px.timeline(
            df, 
            x_start="start_time", 
            x_end="end_time", 
            y="station_name", 
            color="gap_hours",
            hover_data=["gap_hours"],
            title=f"Scraper Data Holes (Gaps > {args.gap_threshold} Hours)",
            labels={"station_name": "Station", "gap_hours": "Gap Duration (Hours)"},
            color_continuous_scale="Reds"
        )
        fig.update_yaxes(autorange="reversed") # Stations read top-to-bottom

    else:
        print("Aggregating daily play counts...")
        # For line and heatmap, daily play counts naturally show the "holes" (drops to 0)
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
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("No data found to plot.")
            sys.exit(0)

        df['play_date'] = pd.to_datetime(df['play_date'])
        
        # We need to fill in missing dates with 0 so the holes actually appear on the charts
        # Create a complete grid of all dates and stations
        all_dates = pd.date_range(start=df['play_date'].min(), end=df['play_date'].max())
        stations = df['station_name'].unique()
        idx = pd.MultiIndex.from_product([stations, all_dates], names=['station_name', 'play_date'])
        
        df = df.set_index(['station_name', 'play_date']).reindex(idx, fill_value=0).reset_index()

        if args.viz_type == 'line':
            print("Generating Line chart...")
            fig = px.line(
                df, 
                x="play_date", 
                y="play_count", 
                color="station_name",
                title="Daily Play Counts per Station (Drops indicate holes)",
                labels={"play_date": "Date", "play_count": "Songs Scraped", "station_name": "Station"}
            )
            
        elif args.viz_type == 'heatmap':
            print("Generating Heatmap...")
            # Pivot the dataframe for the heatmap
            pivot_df = df.pivot(index="station_name", columns="play_date", values="play_count")
            
            fig = px.imshow(
                pivot_df,
                title="Daily Play Counts Heatmap (Dark areas indicate holes)",
                labels=dict(x="Date", y="Station", color="Songs Scraped"),
                aspect="auto",
                color_continuous_scale="Viridis"
            )

    # Save and output
    fig.write_html(args.output)
    print(f"Done! Visualization saved to: {args.output}")
    print(f"Open this file in your web browser to view the interactive graph.")

if __name__ == "__main__":
    main()