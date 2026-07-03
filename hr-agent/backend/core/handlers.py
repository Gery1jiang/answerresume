"""Default EventBus handlers. Importing this module registers all handlers."""
import logging

from core.events import event_bus, EventType, Event

logger = logging.getLogger(__name__)


@event_bus.on(EventType.FILE_UPLOADED)
def _log_file_uploaded(event: Event):
    logger.info("File uploaded: %(file_name)s (%(file_size)s bytes)", event.data)


@event_bus.on(EventType.RESUME_GENERATED)
def _log_resume_generated(event: Event):
    logger.info("Resume generated: id=%(resume_id)s for %(target_job)s", event.data)


@event_bus.on(EventType.JOB_CRAWLED)
def _log_job_crawled(event: Event):
    logger.info("Job crawled: %(count)d jobs from %(platform)s [%(keywords)s/%(city)s]", event.data)


@event_bus.on(EventType.INTERVIEW_CREATED)
def _log_interview_created(event: Event):
    logger.info("Interview created: %(company_name)s - %(job_title)s", event.data)
