class Device {
  final int id;
  final String deviceUid;
  final int farmId;
  final bool isOnline;
  final String? lastHeartbeat;

  Device({
    required this.id,
    required this.deviceUid,
    required this.farmId,
    required this.isOnline,
    this.lastHeartbeat,
  });

  factory Device.fromJson(Map<String, dynamic> json) {
    return Device(
      id: json['id'] as int,
      deviceUid: json['device_uid'] as String,
      farmId: json['farm_id'] as int,
      isOnline: json['status'] == 'online',
      lastHeartbeat: json['last_heartbeat'] as String?,
    );
  }
}
