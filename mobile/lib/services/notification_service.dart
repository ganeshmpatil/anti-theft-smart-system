import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class NotificationService {
  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  static Future<void> init() async {
    if (kIsWeb) {
      debugPrint('[NotificationService] Skipping init on web platform');
      return;
    }
    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettings = InitializationSettings(android: androidSettings);
    await _plugin.initialize(initSettings);
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

  static Future<void> initFirebase() async {
    // Firebase messaging is initialized when google-services.json is present.
    // For now, we use local notifications as the primary channel.
    // When Firebase is configured, FCM tokens are sent to backend via AuthService.
    debugPrint('[NotificationService] Firebase init skipped — no config yet');
  }
}
