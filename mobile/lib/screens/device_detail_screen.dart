import 'package:flutter/material.dart';
import '../models/device.dart';
import '../services/api_client.dart';

class DeviceDetailScreen extends StatefulWidget {
  final Device device;
  const DeviceDetailScreen({super.key, required this.device});

  @override
  State<DeviceDetailScreen> createState() => _DeviceDetailScreenState();
}

class _DeviceDetailScreenState extends State<DeviceDetailScreen> {
  late Device _device;
  bool _sendingCommand = false;
  bool _updatingMonitoring = false;
  bool _updatingSchedule = false;

  @override
  void initState() {
    super.initState();
    _device = widget.device;
  }

  Future<void> _sendCommand(String action) async {
    setState(() => _sendingCommand = true);
    try {
      await ApiClient.post('/commands', {
        'device_id': _device.id,
        'action': action,
        'params': {},
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Command "$action" sent successfully')),
        );
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text(e.message),
              backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _sendingCommand = false);
    }
  }

  Future<void> _toggleMonitoring(bool value) async {
    setState(() => _updatingMonitoring = true);
    try {
      await ApiClient.put(
        '/devices/${_device.id}/monitoring',
        {'monitoring_enabled': value},
      );
      setState(() {
        _device = _device.copyWith(monitoringEnabled: value);
      });
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _updatingMonitoring = false);
    }
  }

  Future<void> _updateSchedule({
    required int startHour,
    required int endHour,
    required bool enabled,
  }) async {
    setState(() => _updatingSchedule = true);
    try {
      await ApiClient.put(
        '/devices/${_device.id}/schedule',
        {
          'start_hour': startHour,
          'end_hour': endHour,
          'enabled': enabled,
        },
      );
      setState(() {
        _device = _device.copyWith(
          scheduleStartHour: startHour,
          scheduleEndHour: endHour,
        );
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Schedule updated')),
        );
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _updatingSchedule = false);
    }
  }

  Future<void> _pickHour({required bool isStart}) async {
    final currentHour = isStart
        ? (_device.scheduleStartHour ?? 6)
        : (_device.scheduleEndHour ?? 18);

    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: currentHour, minute: 0),
      helpText: isStart ? 'Select start hour' : 'Select end hour',
      builder: (context, child) {
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(alwaysUse24HourFormat: true),
          child: child!,
        );
      },
    );

    if (picked != null) {
      final startHour =
          isStart ? picked.hour : (_device.scheduleStartHour ?? 6);
      final endHour =
          isStart ? (_device.scheduleEndHour ?? 18) : picked.hour;

      await _updateSchedule(
        startHour: startHour,
        endHour: endHour,
        enabled: true,
      );
    }
  }

  String _formatHour(int? hour) {
    if (hour == null) return '--:00';
    return '${hour.toString().padLeft(2, '0')}:00';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(_device.deviceUid)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Status card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Icon(
                    Icons.circle,
                    size: 16,
                    color: _device.isOnline ? Colors.green : Colors.red,
                  ),
                  const SizedBox(width: 12),
                  Text(
                    _device.isOnline ? 'Online' : 'Offline',
                    style: theme.textTheme.titleMedium,
                  ),
                  const Spacer(),
                  if (_device.lastHeartbeat != null)
                    Text('Last seen: ${_device.lastHeartbeat}',
                        style: theme.textTheme.bodySmall),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Device Info
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Device Info', style: theme.textTheme.titleMedium),
                  const Divider(),
                  _InfoRow('Device UID', _device.deviceUid),
                  _InfoRow('Device ID', '${_device.id}'),
                  if (_device.batteryPct != null)
                    _InfoRow('Battery', '${_device.batteryPct}%'),
                  if (_device.cpuTemp != null)
                    _InfoRow(
                        'CPU Temp', '${_device.cpuTemp!.toStringAsFixed(1)} C'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Monitoring toggle
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Monitoring', style: theme.textTheme.titleMedium),
                  const Divider(),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _device.monitoringEnabled
                                ? 'Monitoring Active'
                                : 'Monitoring Paused',
                            style: theme.textTheme.bodyLarge,
                          ),
                          Text(
                            'Toggle to enable or disable monitoring',
                            style: theme.textTheme.bodySmall,
                          ),
                        ],
                      ),
                      _updatingMonitoring
                          ? const SizedBox(
                              width: 24,
                              height: 24,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Switch(
                              value: _device.monitoringEnabled,
                              onChanged: _toggleMonitoring,
                            ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Schedule section
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Daily Schedule', style: theme.textTheme.titleMedium),
                      if (_updatingSchedule)
                        const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                    ],
                  ),
                  const Divider(),
                  Text(
                    'Set a daily time window for automatic monitoring',
                    style: theme.textTheme.bodySmall,
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => _pickHour(isStart: true),
                          icon: const Icon(Icons.play_arrow),
                          label: Text(
                              'Start: ${_formatHour(_device.scheduleStartHour)}'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => _pickHour(isStart: false),
                          icon: const Icon(Icons.stop),
                          label: Text(
                              'End: ${_formatHour(_device.scheduleEndHour)}'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          // Commands
          Text('Commands', style: theme.textTheme.titleMedium),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _CommandButton(
                icon: Icons.shield,
                label: 'Arm',
                color: Colors.green,
                onPressed:
                    _sendingCommand ? null : () => _sendCommand('arm'),
              ),
              _CommandButton(
                icon: Icons.shield_outlined,
                label: 'Disarm',
                color: Colors.orange,
                onPressed:
                    _sendingCommand ? null : () => _sendCommand('disarm'),
              ),
              _CommandButton(
                icon: Icons.camera_alt,
                label: 'Snapshot',
                color: Colors.blue,
                onPressed:
                    _sendingCommand ? null : () => _sendCommand('snapshot'),
              ),
              _CommandButton(
                icon: Icons.restart_alt,
                label: 'Reboot',
                color: Colors.red,
                onPressed:
                    _sendingCommand ? null : () => _sendCommand('reboot'),
              ),
            ],
          ),

          if (_sendingCommand) ...[
            const SizedBox(height: 16),
            const Center(child: CircularProgressIndicator()),
          ],
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodySmall),
          Text(value, style: Theme.of(context).textTheme.bodyMedium),
        ],
      ),
    );
  }
}

class _CommandButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback? onPressed;

  const _CommandButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: (MediaQuery.of(context).size.width - 48) / 2,
      child: OutlinedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon, color: color),
        label: Text(label),
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 16),
          side: BorderSide(color: color),
        ),
      ),
    );
  }
}
