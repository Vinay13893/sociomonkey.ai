"""Static contracts for Phase 7 Channel Partner foundation."""

from pathlib import Path


ROOT = Path(__file__).parent
MODEL = (ROOT / 'app/models/channel_partner.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'app/routes/channel_partners.py').read_text(encoding='utf-8')
VISITS = (ROOT / 'app/routes/visits.py').read_text(encoding='utf-8')
GALLERY = (ROOT / 'app/routes/gallery_operations.py').read_text(encoding='utf-8')
EVENTS = (
    ROOT / 'app/services/channel_partner_events.py'
).read_text(encoding='utf-8')
PUSH = (ROOT / 'app/models/push.py').read_text(encoding='utf-8')
MIGRATION = (
    ROOT / 'migrations/phase7_channel_partners_20260723.py'
).read_text(encoding='utf-8')


def test_one_partner_entity_supports_individual_and_organisation():
    assert "class ChannelPartner(db.Model)" in MODEL
    assert "partner_type IN ('INDIVIDUAL','ORGANISATION')" in MODEL
    assert 'ChannelPartnerOrganisation' not in MODEL
    assert 'IndividualChannelPartner' not in MODEL


def test_contacts_projects_assignments_and_notes_are_relationships():
    for model in (
        'ChannelPartnerContact', 'ChannelPartnerProject',
        'ChannelPartnerAssignment', 'ChannelPartnerNote',
    ):
        assert f'class {model}(db.Model)' in MODEL
    assert "('PREFERRED','ACTIVE','HISTORICAL')" in MIGRATION
    assert 'SECONDARY_RM' in MODEL


def test_financial_workflows_are_not_embedded():
    lower = MODEL.lower()
    for forbidden in (
        'commission_amount', 'payout_amount', 'invoice_amount',
        'bank_account', 'payment_status',
    ):
        assert forbidden not in lower


def test_channel_partner_visits_reuse_generic_participants():
    assert "participant_type == 'CHANNEL_PARTNER'" in VISITS
    assert 'Participant Channel Partner' in VISITS
    assert "participant_type='CHANNEL_PARTNER'" in EVENTS
    for forbidden in ('ChannelPartnerVisit', 'channel_partner_visits'):
        assert forbidden not in MODEL + ROUTES + MIGRATION


def test_gallery_reuses_channel_partner_reference():
    assert "'channel_partners':" in GALLERY
    assert "category == 'CHANNEL_PARTNER'" in GALLERY
    assert 'notify_channel_partner_visit' in GALLERY


def test_routes_are_tenant_scoped_and_bounded():
    assert "filter_by(id=partner_id, tenant_id=_tenant_id())" in ROUTES
    assert 'per_page = min(100' in ROUTES
    assert 'limit = min(200' in ROUTES
    assert ".limit(500)" in ROUTES


def test_capabilities_protect_every_mutation_family():
    for capability in (
        'channel_partners.view', 'channel_partners.create',
        'channel_partners.edit', 'channel_partners.archive',
        'channel_partners.assign', 'channel_partners.manage_contacts',
        'channel_partners.manage_projects',
        'channel_partners.reveal_sensitive',
    ):
        assert capability in MIGRATION
    for capability in (
        'channel_partners.create', 'channel_partners.edit',
        'channel_partners.archive', 'channel_partners.assign',
        'channel_partners.manage_contacts',
        'channel_partners.manage_projects',
    ):
        assert f"@require_capability('{capability}', 'TENANT')" in ROUTES


def test_sensitive_fields_are_masked_without_capability():
    assert '_mask_phone' in MODEL
    assert '_mask_email' in MODEL
    assert '_mask_identifier' in MODEL
    assert 'channel_partners.reveal_sensitive' in ROUTES


def test_activity_and_notification_infrastructure_is_reused():
    assert "module='channel_partners'" in ROUTES
    assert 'correlation_id=correlation_id' in EVENTS
    assert 'push_notification' in EVENTS
    assert 'enqueue_channel_partner_event' in EVENTS
    assert 'NotificationEvent' not in MODEL
    assert "'channel_partner_id': self.channel_partner_id" in PUSH


def test_timeline_combines_required_foundations():
    for timeline_type in (
        "'VISIT'", "'NOTE'", "'ASSIGNMENT'", "'ACTIVITY'",
        "'NOTIFICATION'",
    ):
        assert timeline_type in ROUTES
    assert "'future_tasks': []" in ROUTES
    assert "'relationship_key': 'channel_partner_id'" in ROUTES


def test_migration_is_additive_guarded_and_idempotent():
    upper = MIGRATION.upper()
    assert 'EXPECTED_DATABASE_HOST' in MIGRATION
    assert 'CREATE TABLE IF NOT EXISTS' in upper
    assert 'ADD COLUMN IF NOT EXISTS' in upper
    assert 'ON CONFLICT' in upper
    for forbidden in (
        'DROP TABLE', 'TRUNCATE ', 'DELETE FROM ',
        'ALTER TABLE LEADS', 'ALTER TABLE VISITS',
        'UPDATE LEADS', 'UPDATE VISITS',
    ):
        assert forbidden not in upper


def test_future_finance_and_referral_can_reference_stable_partner_id():
    assert 'REFERENCES channel_partners(id)' in MIGRATION
    assert 'channel_partner_id' in MODEL
    assert 'referral' not in MODEL.lower()
