"""Tenant organisation, business-role, reporting, and permission foundation."""

from datetime import datetime

from .base import db


class OrganisationUnit(db.Model):
    __tablename__ = 'organisation_units'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('organisation_units.id'), nullable=True, index=True)
    code = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    unit_type = db.Column(db.String(50), nullable=False, default='GENERAL')
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship('OrganisationUnit', remote_side=[id], foreign_keys=[parent_id])

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'code', name='uq_organisation_unit_tenant_code'),
        db.Index('ix_organisation_units_tenant_parent_active', 'tenant_id', 'parent_id', 'is_active'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'parent_id': self.parent_id,
            'code': self.code,
            'name': self.name,
            'unit_type': self.unit_type,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class OrganisationUnitMembership(db.Model):
    __tablename__ = 'organisation_unit_memberships'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    organisation_unit_id = db.Column(
        db.Integer, db.ForeignKey('organisation_units.id'), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    membership_type = db.Column(db.String(40), nullable=False, default='MEMBER')
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    effective_from = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    effective_to = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    organisation_unit = db.relationship('OrganisationUnit')
    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        db.UniqueConstraint(
            'organisation_unit_id', 'user_id', 'membership_type',
            name='uq_organisation_membership',
        ),
        db.Index(
            'ix_organisation_memberships_tenant_user_active',
            'tenant_id', 'user_id', 'is_active',
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'organisation_unit_id': self.organisation_unit_id,
            'organisation_unit_name': (
                self.organisation_unit.name if self.organisation_unit else None
            ),
            'user_id': self.user_id,
            'membership_type': self.membership_type,
            'is_primary': self.is_primary,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'is_active': self.is_active,
        }


class BusinessRole(db.Model):
    __tablename__ = 'business_roles'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    key = db.Column(db.String(80), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'key', name='uq_business_role_tenant_key'),
        db.Index('ix_business_roles_tenant_active', 'tenant_id', 'is_active'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'key': self.key,
            'display_name': self.display_name,
            'description': self.description,
            'is_system': self.is_system,
            'is_active': self.is_active,
        }


class UserBusinessRole(db.Model):
    __tablename__ = 'user_business_roles'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    business_role_id = db.Column(db.Integer, db.ForeignKey('business_roles.id'), nullable=False, index=True)
    organisation_unit_id = db.Column(
        db.Integer, db.ForeignKey('organisation_units.id'), nullable=True, index=True
    )
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    effective_from = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    effective_to = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    business_role = db.relationship('BusinessRole')
    organisation_unit = db.relationship('OrganisationUnit')

    __table_args__ = (
        db.UniqueConstraint(
            'user_id', 'business_role_id', 'organisation_unit_id',
            name='uq_user_business_role_scope',
        ),
        db.Index('ix_user_business_roles_tenant_user_active', 'tenant_id', 'user_id', 'is_active'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'business_role_id': self.business_role_id,
            'role_key': self.business_role.key if self.business_role else None,
            'role_name': self.business_role.display_name if self.business_role else None,
            'organisation_unit_id': self.organisation_unit_id,
            'is_primary': self.is_primary,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'is_active': self.is_active,
        }


class ReportingRelationship(db.Model):
    __tablename__ = 'reporting_relationships'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    relationship_type = db.Column(db.String(60), nullable=False, default='LINE_MANAGER')
    organisation_unit_id = db.Column(
        db.Integer, db.ForeignKey('organisation_units.id'), nullable=True, index=True
    )
    effective_from = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    effective_to = db.Column(db.DateTime)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])
    manager = db.relationship('User', foreign_keys=[manager_id])
    organisation_unit = db.relationship('OrganisationUnit')

    __table_args__ = (
        db.CheckConstraint('user_id <> manager_id', name='ck_reporting_relationship_not_self'),
        db.UniqueConstraint(
            'user_id', 'manager_id', 'relationship_type', 'organisation_unit_id',
            name='uq_reporting_relationship_scope',
        ),
        db.Index(
            'ix_reporting_relationships_tenant_manager_active',
            'tenant_id', 'manager_id', 'is_active',
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'manager_id': self.manager_id,
            'relationship_type': self.relationship_type,
            'organisation_unit_id': self.organisation_unit_id,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'is_primary': self.is_primary,
            'is_active': self.is_active,
        }


class PermissionDefinition(db.Model):
    __tablename__ = 'permission_definitions'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(140), nullable=False, unique=True)
    module = db.Column(db.String(80), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'module': self.module,
            'action': self.action,
            'description': self.description,
            'is_active': self.is_active,
        }


class RolePermission(db.Model):
    __tablename__ = 'role_permissions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    business_role_id = db.Column(db.Integer, db.ForeignKey('business_roles.id'), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission_definitions.id'), nullable=False, index=True)
    scope_type = db.Column(db.String(40), nullable=False, default='OWN')
    scope_ref_id = db.Column(db.String(80))
    effect = db.Column(db.String(10), nullable=False, default='ALLOW')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    permission = db.relationship('PermissionDefinition')

    __table_args__ = (
        db.CheckConstraint("effect IN ('ALLOW','DENY')", name='ck_role_permission_effect'),
        db.UniqueConstraint(
            'business_role_id', 'permission_id', 'scope_type', 'scope_ref_id',
            name='uq_role_permission_scope',
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'business_role_id': self.business_role_id,
            'permission_key': self.permission.key if self.permission else None,
            'scope_type': self.scope_type,
            'scope_ref_id': self.scope_ref_id,
            'effect': self.effect,
        }


class UserPermissionOverride(db.Model):
    __tablename__ = 'user_permission_overrides'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission_definitions.id'), nullable=False, index=True)
    scope_type = db.Column(db.String(40), nullable=False, default='OWN')
    scope_ref_id = db.Column(db.String(80))
    effect = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.String(300))
    effective_from = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    effective_to = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    permission = db.relationship('PermissionDefinition')

    __table_args__ = (
        db.CheckConstraint("effect IN ('ALLOW','DENY')", name='ck_user_permission_effect'),
        db.UniqueConstraint(
            'user_id', 'permission_id', 'scope_type', 'scope_ref_id',
            name='uq_user_permission_override_scope',
        ),
        db.Index(
            'ix_user_permission_overrides_tenant_user_active',
            'tenant_id', 'user_id', 'is_active',
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'permission_key': self.permission.key if self.permission else None,
            'scope_type': self.scope_type,
            'scope_ref_id': self.scope_ref_id,
            'effect': self.effect,
            'reason': self.reason,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'is_active': self.is_active,
        }


class RoleAssignmentRotation(db.Model):
    """Round-robin cursor for org-scoped auto-assignment (Phase 13d) - one
    row per (tenant, business role key, organisation unit) pool, mirroring
    the existing per-form/per-source rr_last_index columns
    (LeadSourceFormMapping, LeadSource) but generalized since a role+unit
    pool isn't owned by any single source/form."""
    __tablename__ = 'role_assignment_rotations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    business_role_key = db.Column(db.String(80), nullable=False)
    organisation_unit_id = db.Column(
        db.Integer, db.ForeignKey('organisation_units.id'), nullable=False,
    )
    last_index = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id', 'business_role_key', 'organisation_unit_id',
            name='uq_role_assignment_rotation_scope',
        ),
    )
