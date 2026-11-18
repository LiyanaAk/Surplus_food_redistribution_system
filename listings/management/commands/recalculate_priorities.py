from django.core.management.base import BaseCommand
from core.utils import update_all_priorities_and_expiries

class Command(BaseCommand):
    help = 'Recalculates food listing remaining time, updates priorities (NORMAL/HIGH/URGENT), and marks expired listings.'

    def handle(self, *args, **options):
        self.stdout.write("Running automatic priority and expiry recalculation...")
        expired_count, priority_changed_count = update_all_priorities_and_expiries()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully completed: {expired_count} listing(s) marked EXPIRED, {priority_changed_count} listing(s) updated priority."
            )
        )
