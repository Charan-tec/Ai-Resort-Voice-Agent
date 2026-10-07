import asyncio
from typing import Dict, Optional
from app.core.config import settings
from app.core.logging import logger


class EmailWorker:
    """
    Background worker that asynchronously processes reservation confirmation emails
    with exponential backoff and retry handling.
    """

    def __init__(
        self,
        max_retries: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 30.0
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay

        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self):
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._process_queue())
            logger.info("EmailWorker started.")

    async def enqueue(self, email_data: dict):
        """Enqueue an email job."""
        email_data["attempt"] = 0
        await self._queue.put(email_data)

    async def stop(self):
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
        logger.info("EmailWorker stopped.")

    async def _process_queue(self):
        while self._running:
            try:
                job = await self._queue.get()
                recipient = job.get("recipient")
                booking_id = job.get("booking_id")
                attempt = job.get("attempt", 0) + 1
                job["attempt"] = attempt

                try:
                    await self._send_email(job)
                    logger.info(f"Email sent successfully to {recipient} for booking {booking_id}")
                except Exception as exc:
                    logger.error(
                        f"Email sending failed (attempt {attempt}/{self.max_retries}) for {recipient}: {exc}"
                    )
                    if attempt < self.max_retries:
                        delay = min(self.initial_delay * (2 ** (attempt - 1)), self.max_delay)
                        logger.info(f"Re-queueing email for {recipient} in {delay:.1f}s")
                        await asyncio.sleep(delay)
                        await self._queue.put(job)
                    else:
                        logger.critical(f"Email permanently failed after {self.max_retries} attempts: {recipient}")

                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in email worker queue: {e}")
                await asyncio.sleep(1.0)

    async def _send_email(self, job: dict):
        """Perform email dispatch via SendGrid / mock provider."""
        # If API key configured, use real SendGrid
        if settings.SENDGRID_API_KEY:
            try:
                import sendgrid
                from sendgrid.helpers.mail import Mail

                sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
                message = Mail(
                    from_email=settings.EMAIL_FROM,
                    to_emails=job["recipient"],
                    subject=f"Resort Reservation Confirmation: {job['booking_id']}",
                    html_content=(
                        f"<h2>Dear {job.get('guest_name')},</h2>"
                        f"<p>Thank you for choosing Azure Paradise Resort!</p>"
                        f"<p><strong>Confirmation Number:</strong> {job['booking_id']}</p>"
                        f"<p><strong>Dates:</strong> {job.get('check_in')} to {job.get('check_out')}</p>"
                        f"<p><strong>Total Paid:</strong> ${job.get('total_price', 0):.2f} USD</p>"
                    )
                )
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: sg.send(message))
                return
            except Exception as exc:
                raise exc

        # Simulated successful sending in offline or development environments
        await asyncio.sleep(0.05)


email_worker = EmailWorker(
    max_retries=settings.EMAIL_RETRY_MAX_ATTEMPTS,
    initial_delay=settings.EMAIL_RETRY_INITIAL_DELAY,
    max_delay=settings.EMAIL_RETRY_MAX_DELAY
)
