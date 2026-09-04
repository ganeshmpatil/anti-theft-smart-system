class Alert {
  final int id;
  final int deviceId;
  final String alertType;
  final double confidence;
  final String? imagePath;
  final bool acknowledged;
  final String createdAt;

  Alert({
    required this.id,
    required this.deviceId,
    required this.alertType,
    required this.confidence,
    this.imagePath,
    required this.acknowledged,
    required this.createdAt,
  });

  factory Alert.fromJson(Map<String, dynamic> json) {
    return Alert(
      id: json['id'] as int,
      deviceId: json['device_id'] as int,
      alertType: json['alert_type'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      imagePath: json['image_path'] as String?,
      acknowledged: json['acknowledged'] as bool? ?? false,
      createdAt: json['created_at'] as String,
    );
  }
}
