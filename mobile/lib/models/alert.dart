class Alert {
  final int id;
  final int deviceId;
  final String alertType;
  final double confidence;
  final String? imagePath;
  final String? videoPath;
  final bool acknowledged;
  final String createdAt;

  Alert({
    required this.id,
    required this.deviceId,
    required this.alertType,
    required this.confidence,
    this.imagePath,
    this.videoPath,
    required this.acknowledged,
    required this.createdAt,
  });

  bool get hasVideo => videoPath != null && videoPath!.isNotEmpty;

  factory Alert.fromJson(Map<String, dynamic> json) {
    return Alert(
      id: json['id'] as int,
      deviceId: json['device_id'] as int,
      alertType: json['event_type'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      imagePath: json['image_path'] as String?,
      videoPath: json['video_path'] as String?,
      acknowledged: json['acknowledged'] as bool? ?? false,
      createdAt: json['created_at'] as String,
    );
  }
}
