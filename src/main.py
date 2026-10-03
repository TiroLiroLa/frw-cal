"""Main entry point and orchestrator for frw-cal."""

import argparse
import logging
import signal
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import Config
from .calendar_provider import get_calendar_provider
from .display import get_display
from .ui.renderer import CalendarRenderer
from .weather import WeatherProvider

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("frw-cal")

_RUNNING = True


def signal_handler(signum, frame):
    global _RUNNING
    logger.info("Received termination signal. Gracefully exiting...")
    _RUNNING = False


def get_next_daily_target(daily_time_str: str = "00:00") -> datetime:
    """Calculates the next datetime when the daily refresh should occur."""
    now = datetime.now()
    try:
        parts = daily_time_str.split(":")
        hour, minute = int(parts[0]), int(parts[1])
    except Exception:
        hour, minute = 0, 0
    # Add a small buffer (5s) so the clock has safely ticked past the target minute
    target = now.replace(hour=hour, minute=minute, second=5, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def run_cycle(config: Config, force_mock: bool = False):
    """Executes a single fetch, render, and display cycle."""
    now = datetime.now()
    today = now.date()

    # In interval mode, verify active hours (daily mode always executes when triggered)
    if config.refresh_mode == "interval":
        if not (config.active_hours_start <= now.hour <= config.active_hours_end):
            if not (config.midnight_update and now.hour == 0 and now.minute < 30):
                logger.info(
                    f"Current hour {now.hour} is outside active hours "
                    f"[{config.active_hours_start}-{config.active_hours_end}]. Skipping refresh."
                )
                return

    logger.info("=== Starting Calendar Refresh Cycle ===")

    # 1. Fetch Calendar Events
    # Range: from beginning of current month to today + lookahead days
    start_range = today.replace(day=1)
    end_range = today + timedelta(days=max(config.lookahead_days, 31))

    try:
        provider = get_calendar_provider(config)
        events = provider.get_events(start_range, end_range)
        logger.info(f"Retrieved {len(events)} events for date range {start_range} to {end_range}.")
    except Exception as e:
        logger.error(f"Failed to fetch events: {e}", exc_info=True)
        events = []

    # 2. Fetch Weather
    weather_info = None
    if config.weather_enabled:
        try:
            weather_provider = WeatherProvider(
                latitude=config.weather_latitude,
                longitude=config.weather_longitude,
                enabled=config.weather_enabled,
            )
            weather_info = weather_provider.get_weather()
            if weather_info:
                logger.info(
                    f"Weather: {weather_info.temperature}°C - {weather_info.description}"
                )
        except Exception as e:
            logger.warning(f"Failed to fetch weather: {e}")

    # 3. Render UI Images
    renderer = CalendarRenderer(config)
    black_img, red_img = renderer.render(
        current_date=today,
        events=events,
        weather=weather_info,
        last_update=now,
    )

    # 4. Output to Display
    if force_mock:
        # Override display type for this run
        from .display.mock_display import MockDisplay

        display = MockDisplay(width=config.display_width, height=config.display_height)
    else:
        display = get_display(config)

    try:
        display.init()
        display.display(black_img, red_img)
    finally:
        # Always sleep display to protect hardware
        display.sleep()

    logger.info("=== Refresh Cycle Complete ===")


def main():
    parser = argparse.ArgumentParser(description="frw-cal - Smart E-Paper Calendar")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to custom config.yaml file",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute single update cycle and exit immediately",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously in background with scheduled refresh",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Force mock display preview (generates output/preview.png without hardware)",
    )

    args = parser.parse_args()

    # Register signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    config = Config.load(args.config)

    # If running --preview, ensure calendar mode is mock if credentials don't exist
    force_mock = args.preview

    if args.once or args.preview or not args.daemon:
        run_cycle(config, force_mock=force_mock)
        return

    # Daemon mode loop
    if config.refresh_mode == "daily":
        logger.info(
            f"frw-cal daemon started in DAILY mode. Refresh occurs once per day at {config.daily_time}."
        )
        while _RUNNING:
            try:
                run_cycle(config, force_mock=force_mock)
            except Exception as e:
                logger.error(f"Error in refresh cycle: {e}", exc_info=True)

            target_dt = get_next_daily_target(config.daily_time)
            delta = target_dt - datetime.now()
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            logger.info(
                f"Next refresh scheduled for {target_dt.strftime('%Y-%m-%d %H:%M:%S')} "
                f"(in {hours:02d}h {minutes:02d}m {seconds:02d}s). Sleeping..."
            )

            while _RUNNING:
                remaining = (target_dt - datetime.now()).total_seconds()
                if remaining <= 0:
                    break
                time.sleep(min(remaining, 5.0))
    else:
        logger.info(
            f"frw-cal daemon started in INTERVAL mode. Refresh interval: {config.refresh_interval_minutes} minutes."
        )
        while _RUNNING:
            try:
                run_cycle(config, force_mock=force_mock)
            except Exception as e:
                logger.error(f"Error in refresh cycle: {e}", exc_info=True)

            sleep_seconds = config.refresh_interval_minutes * 60
            logger.info(f"Sleeping for {config.refresh_interval_minutes} minutes...")
            slept = 0
            while _RUNNING and slept < sleep_seconds:
                time.sleep(1)
                slept += 1

    logger.info("frw-cal daemon stopped.")


if __name__ == "__main__":
    main()
