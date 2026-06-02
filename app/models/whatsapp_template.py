from datetime import datetime

from .base import db


WHATSAPP_TEMPLATE_CATEGORIES = [
    'greeting',
    'property_intro',
    'follow_up',
    'site_visit_invite',
    'price_offer',
    'payment_plan',
    'booking_confirmation',
    'callback_reminder',
    'document_share',
    'general',
]

DEFAULT_TEMPLATES = [
    {
        'name': 'Initial Greeting',
        'category': 'greeting',
        'body_text': "Hi {{lead_name}}, I'm {{agent_name}} from {{company_name}}. I noticed you enquired about properties. I'd love to help you find your dream home! When is a good time to talk?",
        'variables': ['lead_name', 'agent_name', 'company_name'],
        'sort_order': 1,
    },
    {
        'name': 'Property Introduction',
        'category': 'property_intro',
        'body_text': "Hi {{lead_name}}, sharing details for *{{project_name}}* in {{location}}. Budget range: ₹{{budget_min}} - ₹{{budget_max}} Cr. I've attached the brochure for your reference. Do let me know your thoughts!",
        'variables': ['lead_name', 'project_name', 'location', 'budget_min', 'budget_max'],
        'sort_order': 2,
    },
    {
        'name': 'Follow Up',
        'category': 'follow_up',
        'body_text': "Hi {{lead_name}}, just checking in on your property search. Have you had a chance to review the details I shared? Happy to answer any questions or arrange a site visit at your convenience.",
        'variables': ['lead_name'],
        'sort_order': 3,
    },
    {
        'name': 'Site Visit Invitation',
        'category': 'site_visit_invite',
        'body_text': "Hi {{lead_name}}, we'd love to invite you for a site visit at *{{project_name}}*. The site is located at {{location}}. We can arrange a visit on {{proposed_date}} at {{proposed_time}}. Would that work for you?",
        'variables': ['lead_name', 'project_name', 'location', 'proposed_date', 'proposed_time'],
        'sort_order': 4,
    },
    {
        'name': 'Special Price Offer',
        'category': 'price_offer',
        'body_text': "Hi {{lead_name}}, great news! We have a special limited-time offer on *{{project_name}}*. Price starting at ₹{{special_price}} Cr. This offer is valid only until {{offer_expiry}}. Would you like to know more?",
        'variables': ['lead_name', 'project_name', 'special_price', 'offer_expiry'],
        'sort_order': 5,
    },
    {
        'name': 'Payment Plan Share',
        'category': 'payment_plan',
        'body_text': "Hi {{lead_name}}, as discussed, sharing the flexible payment plan for *{{project_name}}*. Down payment is only {{down_payment}}% with easy EMI options. Please find the payment schedule attached.",
        'variables': ['lead_name', 'project_name', 'down_payment'],
        'sort_order': 6,
    },
    {
        'name': 'Booking Confirmation',
        'category': 'booking_confirmation',
        'body_text': "Dear {{lead_name}}, congratulations on booking your unit at *{{project_name}}*! 🎉 Our team will reach out with the next steps. Thank you for choosing us. We look forward to welcoming you home!",
        'variables': ['lead_name', 'project_name'],
        'sort_order': 7,
    },
    {
        'name': 'Callback Reminder',
        'category': 'callback_reminder',
        'body_text': "Hi {{lead_name}}, this is a quick reminder about our scheduled call today at {{callback_time}}. Looking forward to speaking with you about your property requirements!",
        'variables': ['lead_name', 'callback_time'],
        'sort_order': 8,
    },
    {
        'name': 'Document Sharing',
        'category': 'document_share',
        'body_text': "Hi {{lead_name}}, as requested, sharing the documents for *{{project_name}}*. Please find the attached files. Do let me know if you need any clarification or additional information.",
        'variables': ['lead_name', 'project_name'],
        'sort_order': 9,
    },
    {
        'name': 'General Message',
        'category': 'general',
        'body_text': "Hi {{lead_name}}, hope you are doing well! Just wanted to touch base regarding your property search. Please feel free to reach out anytime. Happy to assist!",
        'variables': ['lead_name'],
        'sort_order': 10,
    },
]


class WhatsAppTemplate(db.Model):
    __tablename__ = 'whatsapp_templates'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False, default='general')
    body_text = db.Column(db.Text, nullable=False)
    variables = db.Column(db.JSON, nullable=True, default=list)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    sort_order = db.Column(db.Integer, default=99, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'name': self.name,
            'category': self.category,
            'body_text': self.body_text,
            'variables': self.variables or [],
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sort_order': self.sort_order,
        }
