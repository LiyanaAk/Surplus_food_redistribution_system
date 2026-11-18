# Surplus Food Redistribution System

> **Share food. Reduce waste. Feed communities.**

A full-stack, responsive web application built with **Python Django**, **Bootstrap 5**, **MySQL / SQLite**, and **OpenStreetMap (Leaflet.js)** that connects food donors (restaurants, hotels, caterers, households) with verified volunteers and beneficiary institutions (orphanages, shelters, old-age homes) to prevent food waste and nourish communities in real time.

---

## 1. Key Features

- **Dynamic Priority & Time Tracking**: Automatically calculates remaining safe consumption hours and flags urgent listings for immediate pickup before food spoils.
- **Race-Condition Protection**: Ensures that only one volunteer can claim a food batch at any given moment using database-level locking.
- **Verification System**: Administrator verification keeps the network secure by approving NGOs, volunteers, and beneficiary shelters before food is claimed or routed.
- **Complete Delivery Tracking**: Step-by-step lifecycle tracking (`Available` &rarr; `Claimed` &rarr; `Collected` &rarr; `In Transit` &rarr; `Delivered`).
- **Direct Homeless Support**: Enables volunteers to deliver hot food directly to homeless individuals and log distribution notes on the spot.
- **Interactive Map & Distance Calculation**: Visualizes food pickup locations and calculates distances between donors, volunteers, and shelters.
- **Real-Time Notifications & Reports**: Instant in-app alerts and downloadable CSV reports for food rescue metrics.

---

## 2. Technology Stack

- **Backend**: Python 3.12, Django 6.1 (Model-View-Template architecture)
- **Database**: SQLite (local default) / MySQL (production-ready)
- **Database Connectivity**: Django ORM with `PyMySQL` driver
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5.3
- **Icons**: Font Awesome 6.5 & Bootstrap Icons 1.11
- **Maps**: OpenStreetMap with Leaflet.js
- **Charts**: Chart.js for redistribution metrics
- **Timezone**: Indian Standard Time (`Asia/Kolkata`)

---

## 3. Database Structure

The database consists of 7 core tables:

1. **`users`**: Manages all user accounts (Donors, NGOs/Volunteers, Beneficiary Institutions, Administrators), contact details, addresses, and verification statuses.
2. **`institutions`**: Stores profiles for beneficiary shelters, orphanages, and old-age homes, including their facility types and capacity.
3. **`food_categories`**: Organizes food into categories (Vegetarian, Cooked Meals, Bakery, Non-Vegetarian, etc.).
4. **`food_listings`**: Stores food donations posted by donors with quantity, preparation time, safe expiration time, priority, and status.
5. **`claims`**: Manages food claims made by verified volunteers, assigned recipients, and distribution notes.
6. **`notifications`**: Stores in-app alerts and notifications for users.
7. **`status_history`**: Audit log recording every status change and timestamp for each food donation.

---

## 4. User Roles

1. **Donor**: Posts surplus food, tracks donations, and views personal contribution history.
2. **NGO / Volunteer**: Searches available food, claims batches, collects, and delivers to shelters or homeless individuals.
3. **Beneficiary Institution**: Registers shelter details, capacity, and views received deliveries.
4. **Administrator**: Oversees the entire platform, approves NGO/institution registrations, manages food categories, configures urgency thresholds, and generates redistribution reports.

---

## 5. Quick Start Guide

### Step 1: Activate Virtual Environment
```powershell
.\venv\Scripts\activate
```

### Step 2: Apply Migrations
```powershell
python manage.py migrate
```

### Step 3: Start the Development Server
```powershell
python manage.py runserver
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
