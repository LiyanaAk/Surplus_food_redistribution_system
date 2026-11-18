from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from institutions.models import Institution
from listings.models import FoodCategory, FoodListing, StatusHistory
from claims.models import Claim
from notifications.models import Notification
from core.models import SystemSetting
from core.utils import update_all_priorities_and_expiries, haversine_distance, suggest_nearest_institutions

class SurplusFoodSystemComprehensiveTests(TestCase):
    def setUp(self):
        # 1. System Settings
        self.settings = SystemSetting.get_settings()
        self.settings.urgent_threshold_minutes = 60
        self.settings.high_threshold_minutes = 180
        self.settings.default_search_radius_km = 10
        self.settings.save()

        # 2. Categories
        self.cat_veg = FoodCategory.objects.create(name='Vegetarian Food')
        self.cat_bakery = FoodCategory.objects.create(name='Bakery')

        # 3. Users
        self.admin = User.objects.create_superuser(
            email='admin@test.org', name='Admin User', password='password123'
        )
        self.donor = User.objects.create_user(
            email='donor@test.org', name='Hotel Donor', password='password123',
            role=User.ROLE_DONOR, address='Civil Lines, City', latitude=27.8974, longitude=78.0880
        )
        self.ngo_approved = User.objects.create_user(
            email='ngo@test.org', name='Relief NGO', password='password123',
            role=User.ROLE_NGO, verification_status=User.STATUS_APPROVED,
            address='Marris Road, City', latitude=27.9000, longitude=78.0850
        )
        self.ngo_pending = User.objects.create_user(
            email='ngopending@test.org', name='Pending NGO', password='password123',
            role=User.ROLE_NGO, verification_status=User.STATUS_PENDING
        )
        self.inst_user = User.objects.create_user(
            email='inst@test.org', name='Peace Orphanage', password='password123',
            role=User.ROLE_INSTITUTION, verification_status=User.STATUS_APPROVED,
            address='Station Road, City', latitude=27.8920, longitude=78.0800
        )
        self.institution = Institution.objects.create(
            user=self.inst_user, institution_type='orphanage', capacity=60
        )

        self.client = Client()

    def test_01_user_roles_and_verification_rules(self):
        """Test user role properties and verification states"""
        self.assertTrue(self.donor.is_donor)
        self.assertTrue(self.donor.is_approved) # Donors auto-approved

        self.assertTrue(self.ngo_approved.is_ngo)
        self.assertTrue(self.ngo_approved.is_approved)

        self.assertTrue(self.ngo_pending.is_ngo)
        self.assertFalse(self.ngo_pending.is_approved) # Pending approval

        self.assertTrue(self.inst_user.is_institution)
        self.assertTrue(self.admin.is_admin_user)

    def test_02_create_food_listing_and_priority_calculation(self):
        """Test donor creates listing, accepts food-safety declaration, and priority is calculated"""
        now = timezone.now()
        listing = FoodListing.objects.create(
            donor=self.donor,
            category=self.cat_veg,
            food_type='Fresh Dal Makhani & Roti',
            quantity=25.0,
            quantity_unit='kg',
            prepared_at=now - timedelta(hours=1),
            usable_until=now + timedelta(minutes=45), # Urgent: <= 60 mins
            pickup_address=self.donor.address,
            latitude=self.donor.latitude,
            longitude=self.donor.longitude,
            food_safety_accepted=True,
            status=FoodListing.STATUS_AVAILABLE
        )
        listing.recalculate_priority_and_status(urgent_thresh=60, high_thresh=180, save=True)

        self.assertEqual(listing.priority, FoodListing.PRIORITY_URGENT)
        self.assertTrue(listing.can_be_edited)
        self.assertTrue(listing.can_be_cancelled)

    def test_03_edit_and_cancel_listing_rules(self):
        """Donor can edit/cancel only before claim"""
        now = timezone.now()
        listing = FoodListing.objects.create(
            donor=self.donor,
            category=self.cat_bakery,
            food_type='Cakes & Biscuits',
            quantity=15,
            quantity_unit='items',
            prepared_at=now - timedelta(hours=2),
            usable_until=now + timedelta(hours=4),
            pickup_address=self.donor.address,
            food_safety_accepted=True,
            status=FoodListing.STATUS_AVAILABLE
        )
        self.assertTrue(listing.can_be_edited)
        self.assertTrue(listing.can_be_cancelled)

        # Simulate claim
        listing.status = FoodListing.STATUS_CLAIMED
        listing.save()
        self.assertFalse(listing.can_be_edited)
        self.assertFalse(listing.can_be_cancelled)

    def test_04_unapproved_ngo_cannot_claim(self):
        """Unapproved NGO cannot claim food"""
        now = timezone.now()
        listing = FoodListing.objects.create(
            donor=self.donor,
            category=self.cat_veg,
            food_type='Paneer Butter Masala',
            quantity=10,
            quantity_unit='kg',
            prepared_at=now - timedelta(hours=1),
            usable_until=now + timedelta(hours=3),
            pickup_address=self.donor.address,
            food_safety_accepted=True,
            status=FoodListing.STATUS_AVAILABLE
        )

        self.client.login(email='ngopending@test.org', password='password123')
        resp = self.client.post(reverse('claims:claim_listing', args=[listing.listing_id]), follow=True)
        self.assertContains(resp, "Your NGO account is pending administrative approval")

        listing.refresh_from_db()
        self.assertEqual(listing.status, FoodListing.STATUS_AVAILABLE)

    def test_05_approved_ngo_claims_listing_and_notifies_donor(self):
        """Approved NGO claims available food; donor is notified"""
        now = timezone.now()
        listing = FoodListing.objects.create(
            donor=self.donor,
            category=self.cat_veg,
            food_type='Rice and Sambar',
            quantity=30,
            quantity_unit='meals',
            prepared_at=now - timedelta(hours=1),
            usable_until=now + timedelta(hours=4),
            pickup_address=self.donor.address,
            food_safety_accepted=True,
            status=FoodListing.STATUS_AVAILABLE
        )

        self.client.login(email='ngo@test.org', password='password123')
        resp = self.client.post(
            reverse('claims:claim_listing', args=[listing.listing_id]),
            {'institution': self.institution.institution_id, 'recipient_note': 'Direct van collection'},
            follow=True
        )
        self.assertContains(resp, "claimed successfully")

        listing.refresh_from_db()
        self.assertEqual(listing.status, FoodListing.STATUS_CLAIMED)

        # Verify claim record in CLAIMS table
        claim = Claim.objects.get(listing=listing, is_active=True)
        self.assertEqual(claim.claimer, self.ngo_approved)
        self.assertEqual(claim.institution, self.institution)

        # Verify notification created for donor
        self.assertTrue(Notification.objects.filter(user=self.donor, listing=listing).exists())

        # Verify StatusHistory created
        self.assertTrue(StatusHistory.objects.filter(listing=listing, status=FoodListing.STATUS_CLAIMED).exists())

    def test_06_release_claim_before_collection(self):
        """Claimant can release a claim before collection, reverting to AVAILABLE"""
        now = timezone.now()
        listing = FoodListing.objects.create(
            donor=self.donor,
            category=self.cat_veg,
            food_type='Vegetable Soup',
            quantity=12,
            quantity_unit='liters',
            prepared_at=now - timedelta(hours=1),
            usable_until=now + timedelta(hours=3),
            pickup_address=self.donor.address,
            food_safety_accepted=True,
            status=FoodListing.STATUS_CLAIMED
        )
        claim = Claim.objects.create(
            listing=listing,
            claimer=self.ngo_approved,
            is_active=True
        )

        self.client.login(email='ngo@test.org', password='password123')
        resp = self.client.post(
            reverse('claims:release_claim', args=[claim.claim_id]),
            {'reason': 'Volunteer unavailable'},
            follow=True
        )
        self.assertContains(resp, "has been released")

        listing.refresh_from_db()
        self.assertEqual(listing.status, FoodListing.STATUS_AVAILABLE)

        claim.refresh_from_db()
        self.assertFalse(claim.is_active)
        self.assertIsNotNone(claim.released_at)

    def test_07_delivery_lifecycle_and_homeless_recipient_logging(self):
        """
        Test full delivery lifecycle:
        CLAIMED -> COLLECTED -> IN_TRANSIT -> DELIVERED
        With manual logging for homeless individuals.
        """
        now = timezone.now()
        listing = FoodListing.objects.create(
            donor=self.donor,
            category=self.cat_veg,
            food_type='Pulao Packets',
            quantity=50,
            quantity_unit='packets',
            prepared_at=now - timedelta(hours=2),
            usable_until=now + timedelta(hours=4),
            pickup_address=self.donor.address,
            food_safety_accepted=True,
            status=FoodListing.STATUS_CLAIMED
        )
        claim = Claim.objects.create(
            listing=listing,
            claimer=self.ngo_approved,
            is_active=True
        )

        self.client.login(email='ngo@test.org', password='password123')

        # 1. Update to COLLECTED
        resp1 = self.client.post(
            reverse('claims:manage_delivery', args=[claim.claim_id]),
            {'status': FoodListing.STATUS_COLLECTED, 'recipient_type': 'homeless'},
            follow=True
        )
        listing.refresh_from_db()
        self.assertEqual(listing.status, FoodListing.STATUS_COLLECTED)

        # 2. Update to IN_TRANSIT
        resp2 = self.client.post(
            reverse('claims:manage_delivery', args=[claim.claim_id]),
            {'status': FoodListing.STATUS_IN_TRANSIT, 'recipient_type': 'homeless'},
            follow=True
        )
        listing.refresh_from_db()
        self.assertEqual(listing.status, FoodListing.STATUS_IN_TRANSIT)

        # 3. Update to DELIVERED with manual logging for homeless individuals
        resp3 = self.client.post(
            reverse('claims:manage_delivery', args=[claim.claim_id]),
            {
                'status': FoodListing.STATUS_DELIVERED,
                'recipient_type': 'homeless',
                'recipient_note': 'Distributed to 50 homeless laborers at City Bus Terminal shelter',
                'meals_delivered': 50,
                'remarks': 'Food served warm directly to people.'
            },
            follow=True
        )
        listing.refresh_from_db()
        self.assertEqual(listing.status, FoodListing.STATUS_DELIVERED)

        claim.refresh_from_db()
        self.assertIsNone(claim.institution) # delivery to homeless individuals has no institution
        self.assertEqual(claim.meals_delivered, 50)
        self.assertIn("City Bus Terminal", claim.recipient_note)

    def test_08_automatic_expiry_engine(self):
        """
        Automatic engine marks overdue AVAILABLE and CLAIMED listings as EXPIRED,
        but protects COLLECTED or IN_TRANSIT food.
        """
        now = timezone.now()
        # Overdue available listing
        l_overdue_available = FoodListing.objects.create(
            donor=self.donor, category=self.cat_veg, food_type='Overdue Bread',
            quantity=10, quantity_unit='items',
            prepared_at=now - timedelta(hours=6),
            usable_until=now - timedelta(minutes=10), # in the past
            pickup_address=self.donor.address, food_safety_accepted=True,
            status=FoodListing.STATUS_AVAILABLE
        )
        # Overdue but already collected food
        l_collected = FoodListing.objects.create(
            donor=self.donor, category=self.cat_veg, food_type='Collected Rice',
            quantity=20, quantity_unit='kg',
            prepared_at=now - timedelta(hours=6),
            usable_until=now - timedelta(minutes=10), # in the past
            pickup_address=self.donor.address, food_safety_accepted=True,
            status=FoodListing.STATUS_COLLECTED
        )

        expired_count, _ = update_all_priorities_and_expiries()

        l_overdue_available.refresh_from_db()
        l_collected.refresh_from_db()

        self.assertEqual(l_overdue_available.status, FoodListing.STATUS_EXPIRED)
        self.assertEqual(l_collected.status, FoodListing.STATUS_COLLECTED) # collected food is NOT expired!

    def test_09_haversine_distance_and_institution_suggestions(self):
        """Test geographical distance calculation and nearest institution suggestion"""
        lat1, lon1 = 27.8974, 78.0880
        lat2, lon2 = 27.8920, 78.0800
        dist = haversine_distance(lat1, lon1, lat2, lon2)
        self.assertIsNotNone(dist)
        self.assertGreater(dist, 0.5)
        self.assertLess(dist, 2.0)

        # Institution suggestions
        now = timezone.now()
        listing = FoodListing.objects.create(
            donor=self.donor, category=self.cat_veg, food_type='Test Curries',
            quantity=10, quantity_unit='kg',
            prepared_at=now, usable_until=now + timedelta(hours=3),
            pickup_address='Civil Lines', latitude=lat1, longitude=lon1,
            food_safety_accepted=True
        )
        suggestions = suggest_nearest_institutions(listing, limit=3)
        self.assertIn(self.institution, suggestions)

    def test_10_reports_generation_and_csv_export(self):
        """Admin can access reports and export CSV"""
        self.client.login(email='admin@test.org', password='password123')
        resp = self.client.get(reverse('reports:reports_dashboard'))
        self.assertEqual(resp.status_code, 200)

        csv_resp = self.client.get(reverse('reports:export_report_csv'))
        self.assertEqual(csv_resp.status_code, 200)
        self.assertEqual(csv_resp['Content-Type'], 'text/csv')
