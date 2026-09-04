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
  bool _sendingCommand = false;

  Future<void> _sendCommand(String action) async {
    setState(() => _sendingCommand = true);
    try {
      await ApiClient.post('/commands', {
        'device_id': widget.device.id,
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

  @override
  Widget build(BuildContext context) {
    final d = widget.device;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(d.deviceUid)),
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
                    color: d.isOnline ? Colors.green : Colors.red,
                  ),
                  const SizedBox(width: 12),
                  Text(
                    d.isOnline ? 'Online' : 'Offline',
                    style: theme.textTheme.titleMedium,
                  ),
                  const Spacer(),
                  if (d.lastHeartbeat != null)
                    Text('Last seen: ${d.lastHeartbeat}',
                        style: theme.textTheme.bodySmall),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Info
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Device Info', style: theme.textTheme.titleMedium),
                  const Divider(),
                  _InfoRow('Device UID', d.deviceUid),
                  _InfoRow('Device ID', '${d.id}'),
                  _InfoRow('Farm ID', '${d.farmId}'),
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
