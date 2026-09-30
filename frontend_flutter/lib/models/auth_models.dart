class User {
  final dynamic id;
  final String email;
  final String? fullName;
  final String? role;
  final String? tenantId;
  final bool isActive;
  final bool mustChangePassword;
  final DateTime? createdAt;

  User({
    this.id,
    required this.email,
    this.fullName,
    this.role,
    this.tenantId,
    this.isActive = true,
    this.mustChangePassword = false,
    this.createdAt,
  });

  bool get isAdmin => role?.toUpperCase() == 'ADMIN';
  bool get isFinanceAdmin => role?.toUpperCase() == 'FINANCE_ADMIN';
  bool get isFinanceUser => role?.toUpperCase() == 'FINANCE_USER' || role?.toUpperCase() == 'FINANCE';

  factory User.fromJson(Map<String, dynamic> json) {
    final emailVal = json['email']?.toString() ??
        json['user_email']?.toString() ??
        json['sub']?.toString() ??
        '';

    final nameVal = json['full_name']?.toString() ??
        json['name']?.toString() ??
        json['display_name']?.toString() ??
        json['username']?.toString() ??
        (emailVal.isNotEmpty ? emailVal.split('@').first : '');

    return User(
      id: json['id'] is int ? json['id'] : json['id']?.toString() ?? json['user_id']?.toString(),
      email: emailVal,
      fullName: nameVal,
      role: json['role']?.toString() ?? json['user_role']?.toString() ?? json['dev_role']?.toString() ?? 'FINANCE_USER',
      tenantId: json['tenant_id']?.toString(),
      isActive: json['is_active'] ?? true,
      mustChangePassword: json['must_change_password'] == true || json['must_change_password'] == 'true',
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'full_name': fullName,
      'role': role,
      'tenant_id': tenantId,
      'is_active': isActive,
      'must_change_password': mustChangePassword,
      'created_at': createdAt?.toIso8601String(),
    };
  }
}

class AuthResponse {
  final String accessToken;
  final String tokenType;
  final User? user;

  AuthResponse({
    required this.accessToken,
    this.tokenType = 'bearer',
    this.user,
  });

  factory AuthResponse.fromJson(Map<String, dynamic> json) {
    User? parsedUser;
    if (json['user'] != null && json['user'] is Map<String, dynamic>) {
      parsedUser = User.fromJson(json['user'] as Map<String, dynamic>);
    } else if (json['data'] != null && json['data'] is Map<String, dynamic>) {
      final dataMap = json['data'] as Map<String, dynamic>;
      if (dataMap['user'] != null && dataMap['user'] is Map<String, dynamic>) {
        parsedUser = User.fromJson(dataMap['user'] as Map<String, dynamic>);
      } else if (dataMap['email'] != null) {
        parsedUser = User.fromJson(dataMap);
      }
    } else if (json['email'] != null) {
      parsedUser = User.fromJson(json);
    }

    final token = json['access_token']?.toString() ??
        json['token']?.toString() ??
        json['accessToken']?.toString() ??
        json['data']?['access_token']?.toString() ??
        '';

    return AuthResponse(
      accessToken: token,
      tokenType: json['token_type']?.toString() ?? json['tokenType']?.toString() ?? 'bearer',
      user: parsedUser,
    );
  }
}

class AdminUser {
  final String id;
  final String email;
  final String? fullName;
  final String role;
  final bool isActive;
  final bool mustChangePassword;
  final DateTime? createdAt;

  AdminUser({
    required this.id,
    required this.email,
    this.fullName,
    required this.role,
    required this.isActive,
    this.mustChangePassword = false,
    this.createdAt,
  });

  factory AdminUser.fromJson(Map<String, dynamic> json) {
    return AdminUser(
      id: json['id']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      fullName: json['full_name']?.toString() ?? json['name']?.toString(),
      role: json['role']?.toString() ?? 'FINANCE_USER',
      isActive: json['is_active'] ?? true,
      mustChangePassword: json['must_change_password'] == true,
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'full_name': fullName,
      'role': role,
      'is_active': isActive,
      'must_change_password': mustChangePassword,
      'created_at': createdAt?.toIso8601String(),
    };
  }
}

class AdminInvitation {
  final String id;
  final String email;
  final String role;
  final String status;
  final String? emailDeliveryStatus;
  final DateTime? expiresAt;
  final DateTime? createdAt;
  final String? invitedByEmail;

  AdminInvitation({
    required this.id,
    required this.email,
    required this.role,
    required this.status,
    this.emailDeliveryStatus,
    this.expiresAt,
    this.createdAt,
    this.invitedByEmail,
  });

  factory AdminInvitation.fromJson(Map<String, dynamic> json) {
    return AdminInvitation(
      id: json['id']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      role: json['role']?.toString() ?? 'FINANCE_USER',
      status: json['status']?.toString() ?? 'PENDING',
      emailDeliveryStatus: json['email_delivery_status']?.toString(),
      expiresAt: json['expires_at'] != null ? DateTime.tryParse(json['expires_at'].toString()) : null,
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
      invitedByEmail: json['invited_by_email']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'role': role,
      'status': status,
      'email_delivery_status': emailDeliveryStatus,
      'expires_at': expiresAt?.toIso8601String(),
      'created_at': createdAt?.toIso8601String(),
      'invited_by_email': invitedByEmail,
    };
  }
}

