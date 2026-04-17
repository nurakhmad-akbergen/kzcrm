# CRM Product Strategy

## Vision

Build a subscription CRM for appointment-based businesses:

- barbershops
- dental clinics
- beauty salons
- massage studios
- small medical practices
- any service business that manages clients, bookings, staff, services, and payments

The product should not be "a barber CRM with extra hacks".
It should be a general booking CRM with vertical templates.

## Product Principle

Core system:

- clients
- staff
- services
- bookings
- payments
- schedule
- analytics
- reminders
- subscriptions

Industry layer:

- terminology
- onboarding templates
- default services
- role presets
- reports specific to niche workflows

Example:

- Barbershop template: master, haircut, beard, commission
- Dental template: doctor, procedure, cabinet, patient visit history

## What Exists Now

The current codebase already has a strong vertical MVP:

- multi-tenant `Shop`
- `Client`
- `Barber`
- `Service`
- `Appointment`
- `Payment`
- daily schedule
- staff settings
- service settings
- basic finance dashboard

This is enough to evolve into a real SaaS foundation.

## Main Product Problem To Solve

Do not build for "everyone" at once.
Build a universal core for businesses with appointments.

The target user is:

- owns a small or medium service business
- needs booking, client history, staff control, revenue tracking
- wants something simple enough to run daily
- is willing to pay monthly if the product saves time and prevents lost clients

## Recommended Positioning

Position the product like this:

"A CRM for appointment-based businesses with fast setup, client tracking, bookings, and revenue control."

Then support niches through templates:

- barbershop
- dentistry
- beauty salon
- clinic

## Architecture Direction

### 1. Keep the SaaS tenant model

Current `Shop` is the right starting point, but it should become something like:

- `Workspace`
- or `Organization`

Inside it:

- business name
- industry type
- timezone
- subscription status
- plan
- owner

### 2. Generalize niche-specific entities

Current naming is too barber-specific.

Recommended domain migration:

- `Shop` -> `Organization`
- `Barber` -> `StaffMember`
- `Client` -> `Customer` or `Client`
- `Service` -> `Service`
- `Appointment` -> `Booking`

For the UI, labels should depend on the selected template:

- barbershop: "Master"
- dentistry: "Doctor"
- salon: "Specialist"

### 3. Add template configuration instead of hardcoding business logic

Need a model like:

- `IndustryTemplate`
- `OrganizationSettings`

Settings should define:

- display labels
- default statuses
- default services
- whether commission is used
- whether room/cabinet/chair is used
- whether medical notes are required

### 4. Introduce roles and team access

To sell on subscription, access control matters.

Minimum roles:

- owner
- admin
- receptionist
- staff member

## Best MVP For Paid SaaS

Do not start with 20 modules.
Make a strong paid MVP around 6 things:

1. Booking calendar
2. Client database and visit history
3. Staff and services management
4. Payments and revenue dashboard
5. Reminders and no-show reduction
6. Subscription billing

If these are reliable, people can pay.

## Product Roadmap

### Phase 1. Stabilize current foundation

Goal:
turn the current app into a clean core CRM.

Tasks:

- rename domain concepts in backend to universal ones
- isolate barber labels to templates/UI layer
- fix timezone and localization
- clean duplicated imports and simplify views
- add better validation around phone numbers and bookings
- prepare production-ready settings
- move from SQLite to PostgreSQL for production

### Phase 2. Multi-industry support

Goal:
one codebase, multiple business templates.

Tasks:

- add `industry_type` to organization
- build onboarding wizard
- create default templates:
  - barbershop
  - dental clinic
  - beauty salon
- dynamic labels in UI
- industry-specific starter data

### Phase 3. Real business value

Goal:
make the product useful enough to retain paying customers.

Tasks:

- customer history timeline
- notes and tags
- booking statuses and reminders
- cancellation / no-show tracking
- repeat booking flow
- daily and monthly analytics
- employee performance dashboard

### Phase 4. Monetization

Goal:
launch subscriptions.

Tasks:

- trial period
- subscription plans
- billing integration
- limits by plan
- reminder quotas
- extra staff seats

## Recommended First Pricing Logic

Simple pricing wins early.

Example:

- Starter: one location, limited staff, basic CRM
- Growth: more staff, analytics, reminders
- Pro: multi-location, advanced permissions, richer reports

You are not selling software only.
You are selling:

- fewer missed appointments
- better repeat visits
- clearer staff control
- easier revenue tracking

## What Will Make This Product Actually Strong

### 1. Fast setup

New business should be able to:

- register
- choose business type
- import or create staff
- add services
- start booking in 10 minutes

### 2. Very clear schedule UX

The calendar is the heart of the system.
If it feels slow or confusing, product value drops immediately.

### 3. Strong client card

Each client should have:

- contacts
- visit history
- total spend
- favorite services
- notes
- last appointment
- next appointment

### 4. Retention tools

Revenue comes not just from first signup, but from retention.
Important later features:

- WhatsApp reminders
- return campaigns
- birthday campaigns
- inactive client lists

## Concrete Gaps In Current Project

Based on the current codebase, the main gaps are:

- naming is niche-specific
- no role system
- no subscription system
- no onboarding by business type
- no reminder engine
- timezone is still `UTC`
- production settings are not hardened enough
- current finance/reporting is still basic

## Best Immediate Technical Plan

### Sprint 1

- introduce `industry_type` on tenant
- add universal terminology layer
- set timezone/localization properly
- prepare base dashboard language for multiple niches

### Sprint 2

- refactor `Barber` into universal staff model
- refactor templates and forms
- add role model and invitations

### Sprint 3

- booking calendar improvements
- customer timeline
- richer payment and KPI dashboards

### Sprint 4

- subscription and trial flow
- plan-based permissions
- production deployment setup

## Recommended Build Strategy

Do this in order:

1. Build a strong single-location appointment CRM core
2. Make the core universal
3. Add vertical templates
4. Add billing
5. Add retention and automation features

If you try to support every industry immediately, the product will become messy.
If you build a universal core first, you can sell to many niches without losing focus.

## My Recommendation For This Codebase

The project should move toward:

- one universal CRM engine
- one template system for niches
- one subscription layer for monetization

Barbershop should become the first template, not the whole product identity.

## Suggested Next Execution Step

The best next implementation step is:

refactor the domain model from barber-specific naming to universal CRM naming while preserving current functionality.

That will create a real foundation for:

- dentistry support
- salon support
- future subscription plans
- better admin roles
- template-driven onboarding
