import 'package:flutter/material.dart';
import 'package:flutter_proj/data/mapdata.dart';

/// start and destination: {"lat": ..., "lon": ...}
typedef RouteRequest = ({Map<String, double> start, Map<String, double> end});

/// pop-up where the user types a start and destination address. It looks both
/// up with the geocode API and only closes once both were found, so typos can
/// be fixed without losing what was typed.
class RouteSearchDialog extends StatefulWidget {
  const RouteSearchDialog({super.key});

  /// Shows the dialog. Returns null if the user cancels.
  static Future<RouteRequest?> show(BuildContext context) {
    return showDialog<RouteRequest>(
      context: context,
      builder: (_) => const RouteSearchDialog(),
    );
  }

  @override
  State<RouteSearchDialog> createState() => _RouteSearchDialogState();
}

class _RouteSearchDialogState extends State<RouteSearchDialog> {
  final _startController = TextEditingController();
  final _endController = TextEditingController();

  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _startController.dispose();
    _endController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final start = _startController.text.trim();
    final end = _endController.text.trim();

    if (start.isEmpty || end.isEmpty) {
      setState(() => _error = 'Enter both a start and a destination address.');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      // Look up both addresses at the same time.
      final coords = await Future.wait([
        MapDataFetch.geocode(start),
        MapDataFetch.geocode(end),
      ]);
      if (!mounted) return;
      Navigator.pop(context, (start: coords[0], end: coords[1]));
    } on GeocodeException catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.message;
      });
    } catch (e) {
      debugPrint('geocode failed: $e');
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error =
            'Could not reach the server. Check your connection and try again.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('New route'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          spacing: 12,
          children: [
            TextField(
              controller: _startController,
              enabled: !_loading,
              autofocus: true,
              textInputAction: TextInputAction.next,
              keyboardType: TextInputType.streetAddress,
              decoration: const InputDecoration(
                labelText: 'Start address',
                hintText: '123 Main St, City, ST',
                prefixIcon: Icon(Icons.trip_origin),
                border: OutlineInputBorder(),
              ),
            ),
            TextField(
              controller: _endController,
              enabled: !_loading,
              textInputAction: TextInputAction.done,
              keyboardType: TextInputType.streetAddress,
              onSubmitted: (_) => _submit(),
              decoration: const InputDecoration(
                labelText: 'Destination address',
                hintText: '456 Oak Ave, City, ST',
                prefixIcon: Icon(Icons.location_on),
                border: OutlineInputBorder(),
              ),
            ),
            if (_error != null)
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _loading ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _loading ? null : _submit,
          child: _loading
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Get route'),
        ),
      ],
    );
  }
}
