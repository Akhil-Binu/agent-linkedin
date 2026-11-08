import time
import random
import logging
from datetime import datetime
from typing import Optional, Callable

logger = logging.getLogger("LinkedBot.Scheduler")

class AutonomousScheduler:
    """
    Manages autonomous recurring engagement loops and posting schedules.
    Enforces quiet hours (night pause) and human jitter to mimic organic user behavior.
    """
    def __init__(
        self,
        interval_hours: float = 4.0,
        quiet_hours_start: int = 23, # 11 PM
        quiet_hours_end: int = 7,    # 7 AM
    ):
        self.interval_seconds = interval_hours * 3600
        self.quiet_hours_start = quiet_hours_start
        self.quiet_hours_end = quiet_hours_end
        self.is_running = False

    def is_quiet_hours(self) -> bool:
        """Determines if local time falls into night quiet hours."""
        now = datetime.now()
        hour = now.hour
        if self.quiet_hours_start > self.quiet_hours_end:
            # Over midnight (e.g., 23 to 7)
            return hour >= self.quiet_hours_start or hour < self.quiet_hours_end
        else:
            return self.quiet_hours_start <= hour < self.quiet_hours_end

    def start_loop(self, task_fn: Callable[[], None], max_iterations: Optional[int] = None):
        """
        Runs the recurring loop with human jitter and quiet hours awareness.
        """
        self.is_running = True
        iteration = 0
        logger.info(f"Starting Autonomous Scheduler (interval: {self.interval_seconds/3600:.1f}h)")

        try:
            while self.is_running:
                iteration += 1
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if self.is_quiet_hours():
                    logger.info(f"[{now_str}] In quiet hours ({self.quiet_hours_start}:00 - {self.quiet_hours_end}:00). Sleeping 30 minutes.")
                    time.sleep(1800)
                    continue

                logger.info(f"\n========================================================")
                logger.info(f"⏰ [CYCLE #{iteration} @ {now_str}] Triggering Scheduled Run")
                logger.info(f"========================================================\n")

                try:
                    task_fn()
                except Exception as e:
                    logger.error(f"Error during scheduled execution cycle: {e}", exc_info=True)

                if max_iterations and iteration >= max_iterations:
                    logger.info(f"Completed maximum requested iterations ({max_iterations}). Stopping.")
                    break

                # Add human jitter (+/- 10 minutes)
                jitter = random.randint(-600, 600)
                sleep_time = max(1800, self.interval_seconds + jitter)
                next_run = datetime.fromtimestamp(time.time() + sleep_time).strftime("%H:%M:%S")
                logger.info(f"Cycle #{iteration} complete. Sleeping {sleep_time/60:.1f} minutes. Next run around ~{next_run}.\n")

                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Autonomous scheduler stopped by user.")
            self.is_running = False
