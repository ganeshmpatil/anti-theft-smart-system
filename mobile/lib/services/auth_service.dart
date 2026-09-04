import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/user.dart';
import 'api_client.dart';

class AuthService extends ChangeNotifier {
  bool _isAuthenticated = false;
  bool _isLoading = true;

  bool get isAuthenticated => _isAuthenticated;
  bool get isLoading => _isLoading;

  AuthService() {
    _checkAuth();
  }

  Future<void> _checkAuth() async {
    final prefs = await SharedPreferences.getInstance();
    _isAuthenticated = prefs.getString('access_token') != null;
    _isLoading = false;
    notifyListeners();
  }

  Future<void> register(
    String phone,
    String password,
    String fullName,
    String address, {
    String? email,
  }) async {
    final body = <String, dynamic>{
      'phone': phone,
      'password': password,
      'full_name': fullName,
      'address': address,
    };
    if (email != null && email.isNotEmpty) {
      body['email'] = email;
    }

    final data = await ApiClient.post('/auth/register', body, auth: false);
    final token = AuthToken.fromJson(data);
    await _saveToken(token);
  }

  Future<void> login(String phone, String password) async {
    final data = await ApiClient.post('/auth/login', {
      'phone': phone,
      'password': password,
    }, auth: false);

    final token = AuthToken.fromJson(data);
    await _saveToken(token);
  }

  Future<Map<String, dynamic>> uploadSelfie(String filePath) async {
    final data = await ApiClient.multipartPost(
      '/auth/selfie',
      'file',
      filePath,
    );
    return Map<String, dynamic>.from(data);
  }

  Future<Map<String, dynamic>> getProfile() async {
    final data = await ApiClient.get('/auth/profile');
    return Map<String, dynamic>.from(data);
  }

  Future<void> _saveToken(AuthToken token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', token.accessToken);
    _isAuthenticated = true;
    notifyListeners();
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    _isAuthenticated = false;
    notifyListeners();
  }

  Future<void> updateFcmToken(String fcmToken) async {
    try {
      await ApiClient.post('/auth/fcm-token', {'fcm_token': fcmToken});
    } catch (_) {
      // Non-critical -- silently ignore
    }
  }
}
