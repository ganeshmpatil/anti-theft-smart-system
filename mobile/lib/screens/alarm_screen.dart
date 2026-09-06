import 'package:flutter/material.dart';
import '../services/alarm_service.dart';

class AlarmScreen extends StatefulWidget {
  final String title;
  final String body;
  final String? imageUrl;

  const AlarmScreen({
    super.key,
    required this.title,
    required this.body,
    this.imageUrl,
  });

  @override
  State<AlarmScreen> createState() => _AlarmScreenState();
}

class _AlarmScreenState extends State<AlarmScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _flashController;

  @override
  void initState() {
    super.initState();
    _flashController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    )..repeat(reverse: true);
    _flashController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _flashController.dispose();
    super.dispose();
  }

  Future<void> _dismiss() async {
    await AlarmService().stop();
    if (mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final flashValue = _flashController.value;

    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor:
            Color.lerp(Colors.red.shade900, Colors.red, flashValue),
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.warning_rounded,
                      color: Colors.white, size: 80),
                  const SizedBox(height: 24),
                  Text(
                    widget.title,
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.bold),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    widget.body,
                    style:
                        const TextStyle(color: Colors.white70, fontSize: 18),
                    textAlign: TextAlign.center,
                  ),
                  if (widget.imageUrl != null) ...[
                    const SizedBox(height: 24),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: Image.network(
                        widget.imageUrl!,
                        height: 200,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) =>
                            const SizedBox.shrink(),
                      ),
                    ),
                  ],
                  const SizedBox(height: 48),
                  SizedBox(
                    width: double.infinity,
                    height: 56,
                    child: ElevatedButton.icon(
                      onPressed: _dismiss,
                      icon: const Icon(Icons.alarm_off, size: 28),
                      label: const Text(
                        'DISMISS ALARM',
                        style: TextStyle(
                            fontSize: 18, fontWeight: FontWeight.bold),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: Colors.red.shade900,
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
