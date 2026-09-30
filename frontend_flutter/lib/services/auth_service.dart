import 'package:dio/dio.dart';
import '../config/api_config.dart';
import '../models/auth_models.dart';
import 'api_client.dart';
import 'storage_service.dart';

class AuthService {
  final ApiClient _client = ApiClient();

  Future<AuthResponse> login(String email, String password) async {
    try {
      final response = await _client.post(
        ApiConfig.login,
        data: {
          'email': email,
          'password': password,
        },
      );

      final authData = AuthResponse.fromJson(response.data);
      if (authData.accessToken.isNotEmpty) {
        await StorageService.saveToken(authData.accessToken);
        await StorageService.saveUser(
          authData.user?.email ?? email,
          authData.user?.fullName,
          authData.user?.role,
          authData.user?.tenantId,
        );
      }
      return authData;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Login failed';
      throw Exception(msg);
    }
  }

  Future<AuthResponse> register(String email, String password, String? fullName) async {
    try {
      final response = await _client.post(
        ApiConfig.signup,
        data: {
          'email': email,
          'password': password,
          'full_name': fullName ?? email.split('@').first,
        },
      );

      final authData = AuthResponse.fromJson(response.data);
      if (authData.accessToken.isNotEmpty) {
        await StorageService.saveToken(authData.accessToken);
        await StorageService.saveUser(
          authData.user?.email ?? email,
          authData.user?.fullName ?? fullName,
          authData.user?.role,
          authData.user?.tenantId,
        );
      }
      return authData;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Registration failed';
      throw Exception(msg);
    }
  }

  Future<AuthResponse> switchDevRole(String role) async {
    try {
      final response = await _client.post(
        ApiConfig.token,
        data: {
          'email': 'finance@sakshi.ai',
          'dev_role': role.toUpperCase(),
          'dev_tenant_id': 'default-tenant-001',
          'dev_name': 'Dev ${role.toUpperCase()}',
        },
      );

      final authData = AuthResponse.fromJson(response.data);
      if (authData.accessToken.isNotEmpty) {
        await StorageService.saveToken(authData.accessToken);
        await StorageService.saveUser(
          authData.user?.email ?? 'finance@sakshi.ai',
          authData.user?.fullName,
          authData.user?.role ?? role.toUpperCase(),
          authData.user?.tenantId,
        );
      }
      return authData;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Role switch failed';
      throw Exception(msg);
    }
  }

  Future<User?> getCurrentUser() async {
    try {
      final token = await StorageService.getToken();
      if (token == null || token.isEmpty) return null;

      final response = await _client.get(
        ApiConfig.me,
        options: Options(
          sendTimeout: const Duration(seconds: 4),
          receiveTimeout: const Duration(seconds: 4),
        ),
      );
      if (response.data is Map<String, dynamic>) {
        final data = response.data as Map<String, dynamic>;
        final userObj = data['user'] is Map<String, dynamic> ? data['user'] as Map<String, dynamic> : data;
        final user = User.fromJson(userObj);
        await StorageService.saveUser(user.email, user.fullName, user.role, user.tenantId);
        return user;
      }
      return null;
    } catch (_) {
      final userMap = await StorageService.getUser();
      if (userMap['email'] != null && userMap['email']!.isNotEmpty) {
        return User(
          email: userMap['email']!,
          fullName: userMap['name'] ?? userMap['email']!.split('@').first,
          role: userMap['role'] ?? 'FINANCE',
          tenantId: userMap['tenant_id'],
        );
      }
      return null;
    }
  }

  Future<Map<String, dynamic>> changePassword(String newPassword) async {
    try {
      final response = await _client.post(
        ApiConfig.changePassword,
        data: {'new_password': newPassword},
      );
      final data = response.data as Map<String, dynamic>;
      if (data['access_token'] != null) {
        await StorageService.saveToken(data['access_token'].toString());
      }
      return data;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Password change failed';
      throw Exception(msg);
    }
  }

  Future<Map<String, dynamic>> verifyInvite(String token) async {
    try {
      final response = await _client.post(
        ApiConfig.verifyInvite,
        data: {'token': token},
      );
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Invalid or expired invitation';
      throw Exception(msg);
    }
  }

  Future<Map<String, dynamic>> sendInviteOtp(String token) async {
    try {
      final response = await _client.post(
        ApiConfig.sendInviteOtp,
        data: {'token': token},
      );
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Failed to send OTP';
      throw Exception(msg);
    }
  }

  Future<Map<String, dynamic>> verifyInviteOtp(String token, String otp) async {
    try {
      final response = await _client.post(
        ApiConfig.verifyInviteOtp,
        data: {'token': token, 'otp': otp.trim()},
      );
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Invalid OTP code';
      throw Exception(msg);
    }
  }

  Future<AuthResponse> acceptInvite({
    required String token,
    required String password,
    String? fullName,
  }) async {
    try {
      final response = await _client.post(
        ApiConfig.acceptInvite,
        data: {
          'token': token,
          'password': password,
          'full_name': fullName?.trim(),
        },
      );
      final authData = AuthResponse.fromJson(response.data);
      if (authData.accessToken.isNotEmpty) {
        await StorageService.saveToken(authData.accessToken);
        await StorageService.saveUser(
          authData.user?.email ?? '',
          authData.user?.fullName ?? fullName,
          authData.user?.role,
          authData.user?.tenantId,
        );
      }
      return authData;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Failed to accept invitation';
      throw Exception(msg);
    }
  }

  Future<void> logout() async {
    await StorageService.clearToken();
  }
}

