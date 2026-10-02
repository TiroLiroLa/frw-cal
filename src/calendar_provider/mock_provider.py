"""Mock calendar provider generating sample events for testing and demonstration."""

from datetime import date, datetime, time, timedelta
from typing import List
from .base import BaseCalendarProvider, CalendarEvent


class MockCalendarProvider(BaseCalendarProvider):
    """Provides realistic sample calendar data in Portuguese for testing."""

    def __init__(self, reference_date: date = None):
        self.reference_date = reference_date or date.today()

    def get_events(self, start_date: date, end_date: date) -> List[CalendarEvent]:
        today = self.reference_date
        events: List[CalendarEvent] = []

        # Today's events
        events.append(
            CalendarEvent(
                summary="Reunião de Planejamento",
                start=datetime.combine(today, time(10, 0)),
                end=datetime.combine(today, time(11, 0)),
                all_day=False,
                location="Google Meet",
            )
        )
        events.append(
            CalendarEvent(
                summary="Consulta Dentista",
                start=datetime.combine(today, time(15, 30)),
                end=datetime.combine(today, time(16, 30)),
                all_day=False,
                location="Clínica Odonto",
            )
        )

        # Tomorrow's events
        tomorrow = today + timedelta(days=1)
        events.append(
            CalendarEvent(
                summary="Entrega Sprint & Deploy",
                start=datetime.combine(tomorrow, time(17, 0)),
                end=datetime.combine(tomorrow, time(18, 0)),
                all_day=False,
            )
        )

        # In 3 days: Birthday
        bday_date = today + timedelta(days=3)
        events.append(
            CalendarEvent(
                summary="Aniversário da Camila 🎉",
                start=datetime.combine(bday_date, time(0, 0)),
                end=datetime.combine(bday_date, time(23, 59)),
                all_day=True,
                is_birthday=True,
            )
        )

        # In 5 days: Evening dinner
        dinner_date = today + timedelta(days=5)
        events.append(
            CalendarEvent(
                summary="Jantar com Amigos",
                start=datetime.combine(dinner_date, time(20, 0)),
                end=datetime.combine(dinner_date, time(22, 30)),
                all_day=False,
            )
        )

        # In 7 days: Aniversário ou compromisso importante
        bday_pedro = today + timedelta(days=7)
        events.append(
            CalendarEvent(
                summary="Aniversário do Pedro 🎂",
                start=datetime.combine(bday_pedro, time(0, 0)),
                end=datetime.combine(bday_pedro, time(23, 59)),
                all_day=True,
                is_birthday=True,
            )
        )

        # In 10 days: Workshop
        workshop_date = today + timedelta(days=10)
        events.append(
            CalendarEvent(
                summary="Workshop Python & IoT",
                start=datetime.combine(workshop_date, time(14, 0)),
                end=datetime.combine(workshop_date, time(18, 0)),
                all_day=False,
            )
        )

        # Add a few events in the month for grid dots (earlier this month if possible)
        first_of_month = today.replace(day=1)
        for offset in [2, 8, 14, 22]:
            try:
                sample_day = first_of_month + timedelta(days=offset)
                if sample_day.month == today.month and sample_day != today and sample_day != tomorrow:
                    events.append(
                        CalendarEvent(
                            summary="Compromisso agendado",
                            start=datetime.combine(sample_day, time(9, 0)),
                            end=datetime.combine(sample_day, time(10, 0)),
                            all_day=False,
                        )
                    )
            except OverflowError:
                pass

        # Filter within requested range and sort
        filtered = [
            e for e in events
            if e.end.date() >= start_date and e.start.date() <= end_date
        ]
        filtered.sort(key=lambda ev: ev.start)
        return filtered
