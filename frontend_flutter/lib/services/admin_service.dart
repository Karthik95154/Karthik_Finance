import 'package:dio/dio.dart';
import '../config/api_config.dart';
import '../models/auth_models.dart';
import 'api_client.dart';

class AdminService {
  final ApiClient _client = ApiClient();

  /// Retrieves all users in the tenant organization.
  Future<List<AdminUser>> getUsers() async {
    try {
      final response = await _client.get(ApiConfig.adminUsers);
      if (response.data is List) {
        return (response.data as List)
            .map((e) => AdminUser.fromJson(e as Map<String, dynamic>))
            .toList();
      }
      return [];
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Failed to load users';
      throw Exception(msg);
    }
  }

  /// Sends an email invitation to a new user with an assigned role.
  Future<Map<String, dynamic>> inviteUser({
    required String email,
    required String role,
    String? fullName,
  }) async {
    try {
      final response = await _client.post(
        ApiConfig.adminInviteUser,
        data: {
          'email': email.trim().toLowerCase(),
          'role': role.toUpperCase(),
          'full_name': fullName?.trim(),
        },
      );
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Failed to send invitation';
      throw Exception(msg);
    }
  }

  /// Directly creates an active user with temporary password and role.
  Future<AdminUser> createDirectUser({
    required String email,
    required String password,
    required String role,
    String? fullName,
  }) async {
    try {
      final response = await _client.post(
        ApiConfig.adminDirectUser,
        data: {
          'email': email.trim().toLowerCase(),
          'password': password,
          'role': role.toUpperCase(),
          'full_name': fullName?.trim(),
        },
      );
      return AdminUser.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Failed to create user directly';
      throw Exception(msg);
    }
  }

  /// Toggles the active/inactive state of a user.
  Future<AdminUser> toggleUserStatus(String userId, bool isActive) async {
    try {
      final response = await _client.patch(
        ApiConfig.adminUserStatus(userId),
        data: {'is_active': isActive},
      );
      return AdminUser.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Failed to update user status';
      throw Exception(msg);
    }
  }

  /// Updates the role of a user.
  Future<AdminUser> updateUserRole(String userId, String role) async {
    try {
      final response = await _client.patch(
        ApiConfig.adminUserRole(userId),
        data: {'role': role.toUpperCase()},
      );
      return AdminUser.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Failed to update user role';
      throw Exception(msg);
    }
  }

  /// Retrieves all outstanding invitations for the tenant.
  Future<List<AdminInvitation>> getInvitations() async {
    try {
      final response = await _client.get(ApiConfig.adminInvitations);
      if (response.data is List) {
        return (response.data as List)
            .map((e) => AdminInvitation.fromJson(e as Map<String, dynamic>))
            .toList();
      }
      return [];
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Failed to load invitations';
      throw Exception(msg);
    }
  }

  /// Resends an invitation email.
  Future<Map<String, dynamic>> resendInvitation(String invitationId) async {
    try {
      final response = await _client.post(ApiConfig.adminResendInvitation(invitationId));
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Failed to resend invitation';
      throw Exception(msg);
    }
  }

  /// Revokes/cancels an outstanding invitation.
  Future<Map<String, dynamic>> revokeInvitation(String invitationId) async {
    try {
      final response = await _client.delete(ApiConfig.adminRevokeInvitation(invitationId));
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Failed to revoke invitation';
      throw Exception(msg);
    }
  }
}
