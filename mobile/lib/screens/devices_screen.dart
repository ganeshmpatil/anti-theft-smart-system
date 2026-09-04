import 'package:flutter/material.dart';
import '../models/device.dart';
import '../services/api_client.dart';
import 'device_detail_screen.dart';

class DevicesScreen extends StatefulWidget {
  const DevicesScreen({super.key});

  @override
  State<DevicesScreen> createState() => _DevicesScreenState();
}

class _DevicesScreenState extends State<DevicesScreen> {
  List<Device> _devices = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final devData = await ApiClient.get('/devices');
      setState(() {
        _devices = (devData as List).map((d) => Device.fromJson(d)).toList();
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e is ApiException ? e.message : 'Failed to load devices';
        _loading = false;
      });
    }
  }

  void _showLinkDeviceDialog() {
    final uidCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Link Device'),
        content: TextField(
          controller: uidCtrl,
          decoration: const InputDecoration(
            labelText: 'Device UID',
            hintText: 'Enter the UID printed on the device',
            border: OutlineInputBorder(),
            prefixIcon: Icon(Icons.qr_code),
          ),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () async {
              final uid = uidCtrl.text.trim();
              if (uid.isEmpty) return;
              try {
                await ApiClient.post('/devices/link', {'device_uid': uid});
                if (ctx.mounted) Navigator.pop(ctx);
                _load();
              } on ApiException catch (e) {
                if (ctx.mounted) {
                  ScaffoldMessenger.of(ctx)
                      .showSnackBar(SnackBar(content: Text(e.message)));
                }
              }
            },
            child: const Text('Link'),
          ),
        ],
      ),
    );
  }

  Future<void> _unlinkDevice(Device device) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Unlink Device'),
        content: Text(
            'Are you sure you want to unlink "${device.deviceUid}"? You will stop receiving alerts from this device.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Unlink'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        await ApiClient.delete('/devices/${device.id}/unlink');
        _load();
      } on ApiException catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context)
              .showSnackBar(SnackBar(content: Text(e.message)));
        }
      }
    }
  }

  Future<void> _toggleMonitoring(Device device) async {
    final newValue = !device.monitoringEnabled;
    try {
      await ApiClient.put(
        '/devices/${device.id}/monitoring',
        {'monitoring_enabled': newValue},
      );
      _load();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Devices'),
        actions: [
          IconButton(
            icon: const Icon(Icons.link),
            tooltip: 'Link Device',
            onPressed: _showLinkDeviceDialog,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_error!,
                          style: const TextStyle(color: Colors.red)),
                      const SizedBox(height: 16),
                      FilledButton(
                          onPressed: _load, child: const Text('Retry')),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: _devices.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.devices,
                                  size: 64,
                                  color: theme.colorScheme.outline),
                              const SizedBox(height: 16),
                              Text('No devices linked',
                                  style: theme.textTheme.titleMedium),
                              const SizedBox(height: 8),
                              Text(
                                'Tap the link button to add a device',
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  color: theme.colorScheme.outline,
                                ),
                              ),
                            ],
                          ),
                        )
                      : ListView.builder(
                          itemCount: _devices.length,
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          itemBuilder: (_, i) {
                            final d = _devices[i];
                            return Card(
                              margin: const EdgeInsets.symmetric(
                                  horizontal: 16, vertical: 4),
                              child: ListTile(
                                leading: Icon(Icons.videocam,
                                    color: d.isOnline
                                        ? Colors.green
                                        : Colors.grey),
                                title: Text(d.deviceUid),
                                subtitle: Row(
                                  children: [
                                    Chip(
                                      label: Text(
                                          d.isOnline ? 'Online' : 'Offline',
                                          style: const TextStyle(fontSize: 11)),
                                      backgroundColor: d.isOnline
                                          ? Colors.green.shade100
                                          : Colors.grey.shade200,
                                      padding: EdgeInsets.zero,
                                      materialTapTargetSize:
                                          MaterialTapTargetSize.shrinkWrap,
                                      visualDensity: VisualDensity.compact,
                                    ),
                                    const SizedBox(width: 8),
                                    if (d.batteryPct != null)
                                      Text('${d.batteryPct}%',
                                          style: theme.textTheme.bodySmall),
                                  ],
                                ),
                                trailing: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Switch(
                                      value: d.monitoringEnabled,
                                      onChanged: (_) => _toggleMonitoring(d),
                                    ),
                                    PopupMenuButton<String>(
                                      onSelected: (val) {
                                        if (val == 'unlink') _unlinkDevice(d);
                                      },
                                      itemBuilder: (_) => [
                                        const PopupMenuItem(
                                          value: 'unlink',
                                          child: Row(
                                            children: [
                                              Icon(Icons.link_off,
                                                  color: Colors.red, size: 20),
                                              SizedBox(width: 8),
                                              Text('Unlink'),
                                            ],
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                                onTap: () async {
                                  await Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder: (_) =>
                                          DeviceDetailScreen(device: d),
                                    ),
                                  );
                                  _load();
                                },
                              ),
                            );
                          },
                        ),
                ),
    );
  }
}
