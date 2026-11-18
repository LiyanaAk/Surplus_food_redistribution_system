from django.core.management.base import BaseCommand
from listings.models import FoodCategory
from core.models import SystemSetting

class Command(BaseCommand):
    help = 'Initializes default food categories and system parameters.'

    def handle(self, *args, **options):
        self.stdout.write("Initializing system configuration...")
        settings_obj = SystemSetting.get_settings()
        settings_obj.urgent_threshold_minutes = 60
        settings_obj.high_threshold_minutes = 180
        settings_obj.default_search_radius_km = 10
        settings_obj.save()

        self.stdout.write("Initializing food categories...")
        categories = [
            'Vegetarian Meals',
            'Non-Vegetarian Meals',
            'Perishable Cooked Food',
            'Bakery & Bread',
            'Fresh Fruits & Vegetables',
            'Packaged / Non-Perishable',
        ]
        for cname in categories:
            FoodCategory.objects.get_or_create(name=cname)

        self.stdout.write(self.style.SUCCESS("System configuration and categories successfully initialized."))
