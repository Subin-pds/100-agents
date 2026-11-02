# CCA-F Domain2: Tool use — calendar is a tool the booking agent calls
# CCA-F Domain1: Agentic loop — memory layer; persists state across the call
# INTERVIEW: In-memory dict simulates a real calendar; swap for Google Calendar / DB in prod

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import date, time


@dataclass
class Slot:
    doctor: str
    date: date
    time: time
    patient: str | None = None
    confirmation: str | None = None

    @property
    def is_free(self) -> bool:
        return self.patient is None


@dataclass
class MockCalendar:
    """In-memory clinic calendar with pre-seeded slots for demo."""

    _slots: list[Slot] = field(default_factory=list)

    def __post_init__(self) -> None:
        doctors = [
            os.getenv("CLINIC_DOCTOR_1", "Dr. Anand"),
            os.getenv("CLINIC_DOCTOR_2", "Dr. Priya"),
            os.getenv("CLINIC_DOCTOR_3", "Dr. Rahul"),
        ]
        # Seed two days × 4 time slots per doctor
        from datetime import date, timedelta
        today = date.today()
        for day_offset in range(2):
            d = today + timedelta(days=day_offset)
            for doctor in doctors:
                for hour in [9, 11, 14, 16]:
                    self._slots.append(Slot(doctor=doctor, date=d, time=time(hour, 0)))

    # ── public API ────────────────────────────────────────────────────────────

    def available_slots(self, doctor: str | None = None, on_date: date | None = None) -> list[Slot]:
        return [
            s for s in self._slots
            if s.is_free
            and (doctor is None or s.doctor.lower() == doctor.lower())
            and (on_date is None or s.date == on_date)
        ]

    def book(self, doctor: str, on_date: date, at_time: time, patient: str) -> Slot | None:
        """Book a slot. Returns the booked slot or None if not available."""
        for slot in self._slots:
            if (
                slot.doctor.lower() == doctor.lower()
                and slot.date == on_date
                and slot.time == at_time
                and slot.is_free
            ):
                slot.patient = patient
                slot.confirmation = f"CONF-{uuid.uuid4().hex[:6].upper()}"
                if os.getenv("DRY_RUN", "true").lower() == "true":
                    # Log only — do not persist
                    import structlog
                    structlog.get_logger().info(
                        "booking_dry_run",
                        confirmation=slot.confirmation,
                        doctor=doctor,
                        date=str(on_date),
                        time=str(at_time),
                        patient=patient,
                    )
                return slot
        return None

    def confirmation_message(self, slot: Slot) -> str:
        """Return Malayalam confirmation string for the booked slot."""
        day_map = {0: "തിങ്കളാഴ്ച", 1: "ചൊവ്വാഴ്ച", 2: "ബുധനാഴ്ച",
                   3: "വ്യാഴാഴ്ച", 4: "വെള്ളിയാഴ്ച", 5: "ശനിയാഴ്ച", 6: "ഞായറാഴ്ച"}
        weekday = day_map[slot.date.weekday()]
        hour = slot.time.hour
        period = "രാവിലെ" if hour < 12 else "ഉച്ചയ്ക്ക്" if hour < 17 else "വൈകുന്നേരം"
        display_hour = hour if hour <= 12 else hour - 12

        return (
            f"{slot.patient} എന്നവരുടെ അപ്പോയ്ൻ്റ്മെൻ്റ് "
            f"{slot.doctor} ന്റെ അടുത്ത് "
            f"{weekday}, {period} {display_hour} മണിക്ക് "
            f"ബുക്ക് ചെയ്തിട്ടുണ്ട്. "
            f"കോൺഫർമേഷൻ നമ്പർ: {slot.confirmation}."
        )


# Singleton used across the app lifecycle
_calendar: MockCalendar | None = None


def get_calendar() -> MockCalendar:
    global _calendar
    if _calendar is None:
        _calendar = MockCalendar()
    return _calendar
