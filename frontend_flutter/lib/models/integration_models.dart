class ZohoConnectionStatus {
  final bool isConnected;
  final String? status;
  final String? organizationName;
  final String? organizationId;
  final String? accountEmail;
  final String? apiDomain;
  final DateTime? tokenExpiresAt;
  final DateTime? lastSyncAt;
  final int accountsCount;
  final int taxesCount;
  final int vendorsCount;
  final String? statusMessage;

  ZohoConnectionStatus({
    this.isConnected = false,
    this.status,
    this.organizationName,
    this.organizationId,
    this.accountEmail,
    this.apiDomain,
    this.tokenExpiresAt,
    this.lastSyncAt,
    this.accountsCount = 0,
    this.taxesCount = 0,
    this.vendorsCount = 0,
    this.statusMessage,
  });

  factory ZohoConnectionStatus.fromJson(Map<String, dynamic> json) {
    return ZohoConnectionStatus(
      isConnected: json['connected'] ?? json['is_connected'] ?? false,
      status: json['status']?.toString(),
      organizationName: json['organization_name']?.toString() ?? json['org_name']?.toString(),
      organizationId: json['organization_id']?.toString() ?? json['org_id']?.toString(),
      accountEmail: json['account_email']?.toString() ?? json['email']?.toString(),
      apiDomain: json['api_domain']?.toString(),
      tokenExpiresAt: json['token_expires_at'] != null ? DateTime.tryParse(json['token_expires_at'].toString()) : null,
      lastSyncAt: json['last_sync_at'] != null ? DateTime.tryParse(json['last_sync_at'].toString()) : null,
      accountsCount: json['accounts_count'] is int ? json['accounts_count'] : int.tryParse(json['accounts_count']?.toString() ?? '0') ?? 0,
      taxesCount: json['taxes_count'] is int ? json['taxes_count'] : int.tryParse(json['taxes_count']?.toString() ?? '0') ?? 0,
      vendorsCount: json['vendors_count'] is int ? json['vendors_count'] : int.tryParse(json['vendors_count']?.toString() ?? '0') ?? 0,
      statusMessage: json['error_message']?.toString() ?? json['status']?.toString(),
    );
  }
}

class EmailConfig {
  final String? imapServer;
  final int? imapPort;
  final String? username;
  final String? password;
  final bool isConnected;
  final DateTime? lastSyncTime;

  EmailConfig({
    this.imapServer = 'imap.gmail.com',
    this.imapPort = 993,
    this.username,
    this.password,
    this.isConnected = false,
    this.lastSyncTime,
  });

  factory EmailConfig.fromJson(Map<String, dynamic> json) {
    final cfg = (json['config'] is Map<String, dynamic>) ? json['config'] : json;
    return EmailConfig(
      imapServer: cfg['imap_server']?.toString() ?? cfg['imap_host']?.toString() ?? 'imap.gmail.com',
      imapPort: cfg['imap_port'] is int ? cfg['imap_port'] : int.tryParse(cfg['imap_port']?.toString() ?? '993') ?? 993,
      username: cfg['email_address']?.toString() ?? cfg['username']?.toString(),
      isConnected: json['status'] == 'connected' || json['is_active'] == true,
      lastSyncTime: json['last_synced_at'] != null ? DateTime.tryParse(json['last_synced_at'].toString()) : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'imap_server': imapServer ?? 'imap.gmail.com',
      'imap_port': imapPort ?? 993,
      'email_address': username ?? '',
      'password': password ?? '',
    };
  }
}

class EmailMessage {
  final String id;
  final String sender;
  final String subject;
  final String? fileName;
  final String? mimeType;
  final int fileSize;
  final String? status;
  final String? documentType;
  final String? financialRelevance;
  final String? invoiceOrigin;
  final String? currency;
  final double? classificationConfidence;
  final String? classificationReason;
  final DateTime? date;
  final List<String> attachments;
  final bool isProcessed;

  EmailMessage({
    required this.id,
    required this.sender,
    required this.subject,
    this.fileName,
    this.mimeType,
    this.fileSize = 0,
    this.status,
    this.documentType,
    this.financialRelevance,
    this.invoiceOrigin = 'INDIAN',
    this.currency = 'INR',
    this.classificationConfidence,
    this.classificationReason,
    this.date,
    this.attachments = const [],
    this.isProcessed = false,
  });

  bool get isIndian => (invoiceOrigin?.toUpperCase() ?? 'INDIAN') == 'INDIAN';
  bool get isForeign => (invoiceOrigin?.toUpperCase() ?? '') == 'FOREIGN' || (currency != null && currency!.toUpperCase() != 'INR');

  factory EmailMessage.fromJson(Map<String, dynamic> json) {
    final fName = json['file_name']?.toString() ?? 'Invoice Attachment';
    final conf = json['classification_confidence'];
    return EmailMessage(
      id: json['id']?.toString() ?? '',
      sender: json['email_sender']?.toString() ?? json['from']?.toString() ?? json['sender']?.toString() ?? '',
      subject: json['email_subject']?.toString() ?? json['subject']?.toString() ?? fName,
      fileName: fName,
      mimeType: json['mime_type']?.toString() ?? 'application/pdf',
      fileSize: json['file_size'] is int ? json['file_size'] : int.tryParse(json['file_size']?.toString() ?? '0') ?? 0,
      status: json['status']?.toString() ?? 'STAGED',
      documentType: json['document_type']?.toString() ?? 'INVOICE',
      financialRelevance: json['financial_relevance']?.toString() ?? 'FINANCIAL',
      invoiceOrigin: json['invoice_origin']?.toString() ?? 'INDIAN',
      currency: json['currency']?.toString() ?? 'INR',
      classificationConfidence: conf is num ? conf.toDouble() : null,
      classificationReason: json['classification_reason']?.toString(),
      date: json['email_received_at'] != null
          ? DateTime.tryParse(json['email_received_at'].toString())
          : (json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null),
      attachments: json['file_name'] != null ? [json['file_name'].toString()] : [],
      isProcessed: json['status'] != null && json['status'] != 'STAGED',
    );
  }
}

class ZohoMasterAccount {
  final String id;
  final String? zohoAccountId;
  final String name;
  final String? code;
  final String? type;
  final bool isActive;

  ZohoMasterAccount({
    required this.id,
    this.zohoAccountId,
    required this.name,
    this.code,
    this.type,
    this.isActive = true,
  });

  factory ZohoMasterAccount.fromJson(Map<String, dynamic> json) {
    return ZohoMasterAccount(
      id: json['id']?.toString() ?? '',
      zohoAccountId: json['zoho_account_id']?.toString() ?? json['account_id']?.toString(),
      name: json['account_name']?.toString() ?? json['name']?.toString() ?? 'Account',
      code: json['account_code']?.toString() ?? json['code']?.toString(),
      type: json['account_type']?.toString() ?? json['type']?.toString(),
      isActive: json['is_active'] == true || json['status'] == 'active',
    );
  }
}

class ZohoMasterTax {
  final String id;
  final String? zohoTaxId;
  final String name;
  final double percentage;
  final String? type;
  final bool isActive;

  ZohoMasterTax({
    required this.id,
    this.zohoTaxId,
    required this.name,
    this.percentage = 0.0,
    this.type,
    this.isActive = true,
  });

  factory ZohoMasterTax.fromJson(Map<String, dynamic> json) {
    final pct = json['tax_percentage'] ?? json['tax_rate'] ?? json['percentage'] ?? json['rate'];
    return ZohoMasterTax(
      id: json['id']?.toString() ?? '',
      zohoTaxId: json['zoho_tax_id']?.toString() ?? json['tax_id']?.toString(),
      name: json['tax_name']?.toString() ?? json['name']?.toString() ?? 'Tax Rate',
      percentage: pct is num ? pct.toDouble() : (double.tryParse(pct?.toString() ?? '0') ?? 0.0),
      type: json['tax_type']?.toString() ?? json['type']?.toString(),
      isActive: json['is_active'] == true || json['status'] == 'active',
    );
  }
}

class ZohoMasterVendor {
  final String id;
  final String? zohoContactId;
  final String name;
  final String? gstin;
  final String? pan;
  final String? approvalStatus;

  ZohoMasterVendor({
    required this.id,
    this.zohoContactId,
    required this.name,
    this.gstin,
    this.pan,
    this.approvalStatus,
  });

  factory ZohoMasterVendor.fromJson(Map<String, dynamic> json) {
    return ZohoMasterVendor(
      id: json['id']?.toString() ?? '',
      zohoContactId: json['zoho_contact_id']?.toString() ?? json['contact_id']?.toString(),
      name: json['vendor_name']?.toString() ?? json['contact_name']?.toString() ?? json['name']?.toString() ?? 'Vendor',
      gstin: json['gstin']?.toString() ?? json['tax_identification_number']?.toString(),
      pan: json['pan']?.toString(),
      approvalStatus: json['approval_status']?.toString() ?? 'APPROVED',
    );
  }
}

class ZohoOrganization {
  final String organizationId;
  final String name;
  final String? currencyCode;
  final String? country;
  final bool isDefault;

  ZohoOrganization({
    required this.organizationId,
    required this.name,
    this.currencyCode,
    this.country,
    this.isDefault = false,
  });

  factory ZohoOrganization.fromJson(Map<String, dynamic> json) {
    return ZohoOrganization(
      organizationId: json['organization_id']?.toString() ?? json['org_id']?.toString() ?? '',
      name: json['name']?.toString() ?? json['organization_name']?.toString() ?? 'Organization',
      currencyCode: json['currency_code']?.toString(),
      country: json['country']?.toString(),
      isDefault: json['is_default_org'] == true || json['is_default'] == true,
    );
  }
}

class ZohoMasterDataSummary {
  final List<ZohoMasterAccount> accounts;
  final List<ZohoMasterTax> taxes;
  final List<ZohoMasterVendor> vendors;
  final int accountsCount;
  final int taxesCount;
  final int vendorsCount;

  ZohoMasterDataSummary({
    this.accounts = const [],
    this.taxes = const [],
    this.vendors = const [],
    this.accountsCount = 0,
    this.taxesCount = 0,
    this.vendorsCount = 0,
  });

  factory ZohoMasterDataSummary.fromJson(Map<String, dynamic> json) {
    final accList = (json['accounts'] as List?)
            ?.whereType<Map<String, dynamic>>()
            .map((a) => ZohoMasterAccount.fromJson(a))
            .toList() ??
        [];
    final taxList = (json['taxes'] as List?)
            ?.whereType<Map<String, dynamic>>()
            .map((t) => ZohoMasterTax.fromJson(t))
            .toList() ??
        [];
    final venList = (json['vendors'] as List?)
            ?.whereType<Map<String, dynamic>>()
            .map((v) => ZohoMasterVendor.fromJson(v))
            .toList() ??
        [];

    return ZohoMasterDataSummary(
      accounts: accList,
      taxes: taxList,
      vendors: venList,
      accountsCount: json['accounts_count'] is int ? json['accounts_count'] : accList.length,
      taxesCount: json['taxes_count'] is int ? json['taxes_count'] : taxList.length,
      vendorsCount: json['vendors_count'] is int ? json['vendors_count'] : venList.length,
    );
  }
}


