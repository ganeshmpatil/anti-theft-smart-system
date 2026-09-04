import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/device.dart';
import '../models/alert.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import 'alerts_screen.dart';
import 'devices_screen.dart';
import 'device_detail_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  List<Device> _devices = [];
  List<Alert> _recentAlerts = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final devicesData = await ApiClient.get('/devices');
      final alertsData = await ApiClient.get('/alerts?limit=5');
      setState(() {
        _devices =
            (devicesData as List).map((d) => Device.fromJson(d)).toList();
        _recentAlerts =
            (alertsData as List).map((a) => Alert.fromJson(a)).toList();
        _loading = false;
      });
    } on ApiException catch (e) {
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to load data';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final onlineCount = _devices.where((d) => d.isOnline).length;
    final unackAlerts = _recentAlerts.where((a) => !a.acknowledged).length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('FarmGuard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => context.read<AuthService>().logout(),
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
                      Text(_error!, style: const TextStyle(color: Colors.red)),
                      const SizedBox(height: 16),
                      FilledButton(
                          onPressed: _loadData, child: const Text('Retry')),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadData,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      // Status cards
                      Row(
                        children: [
                          Expanded(
                            child: _StatusCard(
                              icon: Icons.devices,
                              label: 'Devices',
                              value: '${_devices.length}',
                              subtitle: '$onlineCount online',
                              color: Colors.blue,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _StatusCard(
                              icon: Icons.warning_amber,
                              label: 'Alerts',
                              value: '$unackAlerts',
                              subtitle: 'unacknowledged',
                              color: unackAlerts > 0
                                  ? Colors.red
                                  : Colors.green,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 24),

                      // Devices section
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('Devices',
                              style: theme.textTheme.titleMedium),
                          TextButton(
                            onPressed: () => Navigator.push(
                              context,
                              MaterialPageRoute(
                                  builder: (_) => const DevicesScreen()),
                            ),
                            child: const Text('View All'),
                          ),
                        ],
                      ),
                      if (_devices.isEmpty)
                        const Card(
                          child: Padding(
                            padding: EdgeInsets.all(24),
                            child: Text('No devices registered yet.',
                                textAlign: TextAlign.center),
                          ),
                        )
                      else
                        ..._devices.take(3).map((d) => Card(
                              child: ListTile(
                                leading: Icon(
                                  Icons.videocam,
                                  color: d.isOnline
                                      ? Colors.green
                                      : Colors.grey,
                                ),
                                title: Text(d.deviceUid),
                                subtitle: Text(
                                    d.isOnline ? 'Online' : 'Offline'),
                                trailing:
                                    const Icon(Icons.chevron_right),
                                onTap: () => Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) =>
                                        DeviceDetailScreen(device: d),
                                  ),
                                ),
                              ),
                            )),

                      const SizedBox(height: 24),

                      // Recent alerts
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('Recent Alerts',
                              style: theme.textTheme.titleMedium),
                          TextButton(
                            onPressed: () => Navigator.push(
                              context,
                              MaterialPageRoute(
                                  builder: (_) => const AlertsScreen()),
                            ),
                            child: const Text('View All'),
                          ),
                        ],
                      ),
                      if (_recentAlerts.isEmpty)
                        const Card(
                          child: Padding(
                            padding: EdgeInsets.all(24),
                            child: Text('No alerts yet.',
                                textAlign: TextAlign.center),
                          ),
                        )
                      else
                        ..._recentAlerts.map((a) => Card(
                              color: a.acknowledged
                                  ? null
                                  : theme.colorScheme.errorContainer,
                              child: ListTile(
                                leading: Icon(
                                  Icons.warning,
                                  color: a.acknowledged
                                      ? Colors.grey
                                      : Colors.red,
                                ),
                                title: Text(
                                    '${a.alertType} — ${(a.confidence * 100).toStringAsFixed(0)}%'),
                                subtitle: Text(a.createdAt),
                                trailing: a.acknowledged
                                    ? const Icon(Icons.check_circle,
                                        color: Colors.green)
                                    : null,
                              ),
                            )),
                    ],
                  ),
                ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final String subtitle;
  final Color color;

  const _StatusCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.subtitle,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(height: 8),
            Text(value,
                style: Theme.of(context)
                    .textTheme
                    .headlineMedium
                    ?.copyWith(fontWeight: FontWeight.bold)),
            Text(label, style: Theme.of(context).textTheme.bodySmall),
            Text(subtitle,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: color)),
          ],
        ),
      ),
    );
  }
}
