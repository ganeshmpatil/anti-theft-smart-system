class Device {
  final int id;
  final String deviceUid;
  final bool isOnline;
  final String? lastHeartbeat;
  final int? batteryPct;
  final double? cpuTemp;
  final bool monitoringEnabled;
  final String? suspendedUntil;
  final int? scheduleStartHour;
  final int? scheduleEndHour;

  Device({
    required this.id,
    required this.deviceUid,
    required this.isOnline,
    this.lastHeartbeat,
    this.batteryPct,
    this.cpuTemp,
    this.monitoringEnabled = false,
    this.suspendedUntil,
    this.scheduleStartHour,
    this.scheduleEndHour,
  });

  bool get isSuspended {
    if (suspendedUntil == null) return false;
    final until = DateTime.tryParse(suspendedUntil!);
    if (until == null) return false;
    return until.isAfter(DateTime.now().toUtc());
  }

  factory Device.fromJson(Map<String, dynamic> json) {
    return Device(
      id: json['id'] as int,
      deviceUid: json['device_uid'] as String,
      isOnline: json['status'] == 'online',
      lastHeartbeat: json['last_heartbeat'] as String?,
      batteryPct: json['battery_pct'] as int?,
      cpuTemp: (json['cpu_temp'] as num?)?.toDouble(),
      monitoringEnabled: json['monitoring_enabled'] as bool? ?? false,
      suspendedUntil: json['suspended_until'] as String?,
      scheduleStartHour: json['schedule_start_hour'] as int?,
      scheduleEndHour: json['schedule_end_hour'] as int?,
    );
  }

  Device copyWith({
    bool? monitoringEnabled,
    String? suspendedUntil,
    bool clearSuspension = false,
    int? scheduleStartHour,
    int? scheduleEndHour,
  }) {
    return Device(
      id: id,
      deviceUid: deviceUid,
      isOnline: isOnline,
      lastHeartbeat: lastHeartbeat,
      batteryPct: batteryPct,
      cpuTemp: cpuTemp,
      monitoringEnabled: monitoringEnabled ?? this.monitoringEnabled,
      suspendedUntil: clearSuspension ? null : (suspendedUntil ?? this.suspendedUntil),
      scheduleStartHour: scheduleStartHour ?? this.scheduleStartHour,
      scheduleEndHour: scheduleEndHour ?? this.scheduleEndHour,
    );
  }
}
