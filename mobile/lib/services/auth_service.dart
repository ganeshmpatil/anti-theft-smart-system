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

  Future<void> register(String email, String password, String fullName) async {
    final data = await ApiClient.post('/auth/register', {
      'email': email,
      'password': password,
      'full_name': fullName,
    }, auth: false);

    final token = AuthToken.fromJson(data);
    await _saveToken(token);
  }

  Future<void> login(String email, String password) async {
    final data = await ApiClient.post('/auth/login', {
      'email': email,
      'password': password,
    }, auth: false);

    final token = AuthToken.fromJson(data);
    await _saveToken(token);
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
      // Non-critical — silently ignore
    }
  }
}
