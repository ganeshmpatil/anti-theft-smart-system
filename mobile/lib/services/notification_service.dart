import 'package:flutter/foundation.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'api_client.dart';

/// Handles background FCM messages (must be top-level function).
@pragma('vm:entry-point')
Future<void> _firebaseBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  debugPrint('[FCM] Background message: ${message.messageId}');
}

class NotificationService {
  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  static Future<void> init() async {
    if (kIsWeb) {
      debugPrint('[NotificationService] Skipping init on web platform');
      return;
    }

    // Initialize local notifications
    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettings = InitializationSettings(android: androidSettings);
    await _plugin.initialize(initSettings);

    // Initialize Firebase
    await Firebase.initializeApp();

    // Set up background handler
    FirebaseMessaging.onBackgroundMessage(_firebaseBackgroundHandler);

    // Request notification permission
    final messaging = FirebaseMessaging.instance;
    final settings = await messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );
    debugPrint('[FCM] Permission: ${settings.authorizationStatus}');

    // Get and register FCM token
    final token = await messaging.getToken();
    if (token != null) {
      debugPrint('[FCM] Token: ${token.substring(0, 20)}...');
      await _registerToken(token);
    }

    // Listen for token refresh
    messaging.onTokenRefresh.listen(_registerToken);

    // Handle foreground messages — show as local notification
    FirebaseMessaging.onMessage.listen(_handleForegroundMessage);
  }

  static Future<void> _registerToken(String token) async {
    try {
      await ApiClient.post('/auth/fcm-token', {'fcm_token': token});
      debugPrint('[FCM] Token registered with backend');
    } catch (e) {
      debugPrint('[FCM] Failed to register token: $e');
    }
  }

  static void _handleForegroundMessage(RemoteMessage message) {
    final notification = message.notification;
    if (notification == null) return;

    showAlert(
      id: message.hashCode,
      title: notification.title ?? 'Alert',
      body: notification.body ?? '',
    );
  }

  static Future<void> showAlert({
    required int id,
    required String title,
    required String body,
  }) async {
    if (kIsWeb) {
      debugPrint('[NotificationService] Web alert: $title — $body');
      return;
    }
    const androidDetails = AndroidNotificationDetails(
      'farm_alerts',
      'Farm Alerts',
      channelDescription: 'Intrusion detection alerts from your farm',
      importance: Importance.max,
      priority: Priority.high,
    );
    const details = NotificationDetails(android: androidDetails);
    await _plugin.show(id, title, body, details);
  }
}
