import 'package:flutter/material.dart';
import '../models/device.dart';
import '../models/farm.dart';
import '../services/api_client.dart';
import 'device_detail_screen.dart';

class DevicesScreen extends StatefulWidget {
  const DevicesScreen({super.key});

  @override
  State<DevicesScreen> createState() => _DevicesScreenState();
}

class _DevicesScreenState extends State<DevicesScreen> {
  List<Device> _devices = [];
  List<Farm> _farms = [];
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
      final farmData = await ApiClient.get('/farms');
      setState(() {
        _devices = (devData as List).map((d) => Device.fromJson(d)).toList();
        _farms = (farmData as List).map((f) => Farm.fromJson(f)).toList();
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e is ApiException ? e.message : 'Failed to load devices';
        _loading = false;
      });
    }
  }

  String _farmName(int farmId) {
    final farm = _farms.where((f) => f.id == farmId).firstOrNull;
    return farm?.name ?? 'Unknown Farm';
  }

  void _showAddDeviceDialog() {
    if (_farms.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Create a farm first')),
      );
      return;
    }

    final uidCtrl = TextEditingController();
    int selectedFarmId = _farms.first.id;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Register Device'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<int>(
                value: selectedFarmId,
                decoration: const InputDecoration(labelText: 'Farm'),
                items: _farms
                    .map((f) =>
                        DropdownMenuItem(value: f.id, child: Text(f.name)))
                    .toList(),
                onChanged: (v) =>
                    setDialogState(() => selectedFarmId = v ?? selectedFarmId),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: uidCtrl,
                decoration:
                    const InputDecoration(labelText: 'Device UID (e.g. cam-01)'),
              ),
            ],
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Cancel')),
            FilledButton(
              onPressed: () async {
                if (uidCtrl.text.trim().isEmpty) return;
                try {
                  await ApiClient.post('/devices', {
                    'device_uid': uidCtrl.text.trim(),
                    'farm_id': selectedFarmId,
                  });
                  if (ctx.mounted) Navigator.pop(ctx);
                  _load();
                } on ApiException catch (e) {
                  if (ctx.mounted) {
                    ScaffoldMessenger.of(ctx)
                        .showSnackBar(SnackBar(content: Text(e.message)));
                  }
                }
              },
              child: const Text('Register'),
            ),
          ],
        ),
      ),
    );
  }

  void _showAddFarmDialog() {
    final nameCtrl = TextEditingController();
    final locationCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Create Farm'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
                controller: nameCtrl,
                decoration: const InputDecoration(labelText: 'Farm Name')),
            const SizedBox(height: 12),
            TextField(
                controller: locationCtrl,
                decoration:
                    const InputDecoration(labelText: 'Location (optional)')),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              if (nameCtrl.text.trim().isEmpty) return;
              try {
                await ApiClient.post('/farms', {
                  'name': nameCtrl.text.trim(),
                  'location': locationCtrl.text.trim(),
                });
                if (ctx.mounted) Navigator.pop(ctx);
                _load();
              } on ApiException catch (e) {
                if (ctx.mounted) {
                  ScaffoldMessenger.of(ctx)
                      .showSnackBar(SnackBar(content: Text(e.message)));
                }
              }
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Devices'),
        actions: [
          IconButton(
            icon: const Icon(Icons.agriculture),
            tooltip: 'Add Farm',
            onPressed: _showAddFarmDialog,
          ),
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Add Device',
            onPressed: _showAddDeviceDialog,
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
                      ? const Center(child: Text('No devices registered'))
                      : ListView.builder(
                          itemCount: _devices.length,
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
                                subtitle: Text(_farmName(d.farmId)),
                                trailing: Chip(
                                  label: Text(d.isOnline ? 'Online' : 'Offline'),
                                  backgroundColor: d.isOnline
                                      ? Colors.green.shade100
                                      : Colors.grey.shade200,
                                ),
                                onTap: () => Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) =>
                                        DeviceDetailScreen(device: d),
                                  ),
                                ),
                              ),
                            );
                          },
                        ),
                ),
    );
  }
}
