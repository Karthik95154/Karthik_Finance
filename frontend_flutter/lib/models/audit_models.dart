class AuditLogEntry {
  final String id;
  final String action;
  final String? fieldName;
  final String? beforeValue;
  final String? afterValue;
  final String? reason;
  final String? userEmail;
  final DateTime? createdAt;

  AuditLogEntry({
    required this.id,
    required this.action,
    this.fieldName,
    this.beforeValue,
    this.afterValue,
    this.reason,
    this.userEmail,
    this.createdAt,
  });

  factory AuditLogEntry.fromJson(Map<String, dynamic> json) {
    return AuditLogEntry(
      id: json['id']?.toString() ?? '',
      action: json['action']?.toString() ?? 'UPDATE',
      fieldName: json['field_name']?.toString(),
      beforeValue: json['before_value']?.toString(),
      afterValue: json['after_value']?.toString(),
      reason: json['reason']?.toString(),
      userEmail: json['user_email']?.toString(),
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
    );
  }
}
