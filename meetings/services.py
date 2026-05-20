from __future__ import annotations


def prepare_meeting_for_save(meeting, *, actor, change):
    if not change and not meeting.uploaded_by_id:
        meeting.uploaded_by = actor
    return meeting