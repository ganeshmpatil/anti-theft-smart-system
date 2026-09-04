class Device {
  final int id;
  final String deviceUid;
  final int farmId;
  final bool isOnline;
  final String? lastSeen;

  Device({
    required this.id,
    required this.deviceUid,
    required this.farmId,
    required this.isOnline,
    this.lastSeen,
  });

  factory Device.fromJson(Map<String, dynamic> json) {
    return Device(
      id: json['id'] as int,
      deviceUid: json['device_uid'] as String,
      farmId: json['farm_id'] as int,
      isOnline: json['is_online'] as bool? ?? false,
      lastSeen: json['last_seen'] as String?,
    );
  }
}
