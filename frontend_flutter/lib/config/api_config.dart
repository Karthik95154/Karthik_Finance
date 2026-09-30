import 'package:flutter/foundation.dart';

class ApiConfig {
  static String _baseUrl = kIsWeb
      ? 'http://localhost:8000'
      : (defaultTargetPlatform == TargetPlatform.android
          ? 'http://10.0.2.2:8000'
          : 'http://localhost:8000');

  static String get baseUrl => _baseUrl;

  static set baseUrl(String url) {
    if (url.endsWith('/')) {
      _baseUrl = url.substring(0, url.length - 1);
    } else {
      _baseUrl = url;
    }
  }

  static const Duration connectTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 60);
  static const Duration sendTimeout = Duration(seconds: 60);

  // Health
  static String get health => '/api/v1/health';

  // Auth
  static String get login => '/api/v1/auth/login';
  static String get token => '/api/v1/auth/token';
  static String get signup => '/api/v1/auth/signup';
  static String get register => '/api/v1/auth/signup';
  static String get me => '/api/v1/auth/me';
  static String get devSwitchRole => '/api/v1/auth/dev-switch-role';

  // Invoices & Review Pipeline
  static String get invoices => '/api/v1/invoices';
  static String get invoiceUpload => '/api/v1/invoices/upload';
  static String invoiceDetail(dynamic id) => '/api/v1/invoices/$id';
  static String invoiceStatus(dynamic id) => '/api/v1/invoices/$id/status';
  static String invoiceUpdate(dynamic id) => '/api/v1/invoices/$id';
  static String invoiceFile(dynamic id) => '/api/v1/invoices/$id/file';
  static String invoicePages(dynamic id) => '/api/v1/invoices/$id/pages';
  static String invoiceCategorize(dynamic id) => '/api/v1/invoices/$id/categorize';
  static String invoiceJournal(dynamic id) => '/api/v1/invoices/$id/journal';
  static String invoicePeriodDecision(dynamic id) => '/api/v1/invoices/$id/period-decision';

  // Statutory Approvals & Review
  static String invoiceApprove(dynamic id) => '/api/v1/review/invoices/$id/approve';
  static String invoiceReject(dynamic id) => '/api/v1/review/invoices/$id/reject';
  static String invoiceJournalApprove(dynamic id) => '/api/v1/invoices/$id/journal/approve';
  static String invoiceTdsApprove(dynamic id) => '/api/v1/invoices/$id/tds/approve';
  static String invoiceAuditTrail(dynamic id) => '/api/v1/invoices/$id/audit-trail';
  static String invoiceClassificationOverride(dynamic id) => '/api/v1/review/invoices/$id/classification/override';
  static String get metrics => '/api/v1/invoices/metrics/dashboard';

  // Zoho Books Integration
  static String get zohoStatus => '/api/v1/zoho/status';
  static String get zohoAuthUrl => '/api/v1/zoho/connect';
  static String get zohoOrganizations => '/api/v1/zoho/organizations';
  static String get zohoSelectOrg => '/api/v1/zoho/select-org';
  static String get zohoSync => '/api/v1/zoho/sync';
  static String get zohoMasterData => '/api/v1/zoho/master-data';
  static String get zohoMasterDataSummary => '/api/v1/zoho/master-data-summary';
  static String get zohoDisconnect => '/api/v1/zoho/disconnect';
  static String invoiceExportZoho(dynamic id) => '/api/v1/zoho/export-bill/$id';
  static String get zohoCreateCoa => '/api/v1/zoho/chart_of_accounts/create';
  static String get zohoMatchCoa => '/api/v1/zoho/chart_of_accounts/match';

  // Zoho Vendor Resolution on Invoice
  static String invoiceVendorStatus(dynamic id) => '/api/v1/invoices/$id/vendor/status';
  static String invoiceAddVendorToZoho(dynamic id) => '/api/v1/invoices/$id/vendor/add-to-zoho';

  // IMAP Inbox & Staging
  static String get stagedInbox => '/api/v1/inbox/staged';
  static String stagedProcess(dynamic id) => '/api/v1/inbox/staged/$id/process';
  static String stagedDelete(dynamic id) => '/api/v1/inbox/staged/$id';
  static String get emailPoll => '/api/v1/inbox/poll';
  static String get emailConfig => '/api/v1/settings/integrations/imap_email';
  static String get emailConfigure => '/api/v1/settings/integrations/imap_email/configure';
  static String get emailDisconnect => '/api/v1/settings/integrations/imap_email/disconnect';

  // Auth & Invitations
  static String get changePassword => '/api/v1/auth/change-password';
  static String get verifyInvite => '/api/v1/auth/verify-invite';
  static String get sendInviteOtp => '/api/v1/auth/send-invite-otp';
  static String get verifyInviteOtp => '/api/v1/auth/verify-invite-otp';
  static String get acceptInvite => '/api/v1/auth/accept-invite';

  // Administration (Users & Access)
  static String get adminUsers => '/api/v1/admin/users';
  static String get adminInviteUser => '/api/v1/admin/users/invite';
  static String get adminDirectUser => '/api/v1/admin/users/direct';
  static String adminUserStatus(String userId) => '/api/v1/admin/users/$userId/status';
  static String adminUserRole(String userId) => '/api/v1/admin/users/$userId/role';
  static String get adminInvitations => '/api/v1/admin/invitations';
  static String adminResendInvitation(String invId) => '/api/v1/admin/invitations/$invId/resend';
  static String adminRevokeInvitation(String invId) => '/api/v1/admin/invitations/$invId';

  // Forex & RBI Reference Rates
  static String get forexRates => '/api/v1/forex/rates';
  static String get forexConvert => '/api/v1/forex/convert';
}

