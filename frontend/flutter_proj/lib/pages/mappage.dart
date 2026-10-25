import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_proj/data/mapdata.dart';
import 'package:flutter_proj/pages/profilepage.dart';
import 'package:flutter_proj/pages/subpages/mappage/route_map.dart';
import 'package:flutter_proj/pages/subpages/mappage/route_search_dialog.dart';
import 'package:date_time_format/date_time_format.dart';

class MapPage extends StatefulWidget {
  const MapPage({super.key});

  @override
  State<MapPage> createState() => _MapPageState();
}

class _MapPageState extends State<MapPage> {
  // How much of the map is covered by the search bar (top) and summary card
  // (bottom). The map uses these to frame the route in the visible area.
  static const topInset = 0.0;
  static const bottomInset = 210.0;
  // null route + null error = still loading
  RouteData? route;
  String? error;

  // Current start and destination as {"lat": ..., "lon": ...}. These are the
  // default route shown on launch
  Map<String, double> start = {"lat": 39.326432, "lon": -77.339112};
  Map<String, double> end = {"lat": 39.330815, "lon": -77.351600};

  @override
  void initState() {
    super.initState();
    fetchMap();
  }

  // get the map data
  Future<void> fetchMap() async {
    try {
      final data = await MapDataFetch.fetchRouteData(start, end);
      if (!mounted) return;
      setState(() => route = data);
    } catch (e) {
      debugPrint('fetchMap failed: $e');
      if (!mounted) return;
      setState(
        () => error =
            'Could not load the route. Check your connection and try again.',
      );
    }
  }

  void retry() {
    setState(() => error = null);
    fetchMap();
  }

  // opens the address dialog, then loads the route between the two addresses
  void changeRoute() async {
    final result = await RouteSearchDialog.show(context);
    if (result == null || !mounted) return; // cancelled

    setState(() {
      start = result.start;
      end = result.end;
      route = null; // back to the loading spinner
      error = null;
    });
    fetchMap();
  }

  @override
  void dispose() {
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final data = route;

    // The map is the bottom layer and fills the whole page; the search bar and
    // summary card float on top of it.
    return Stack(
      children: [
        Positioned.fill(child: _buildMap(data)),
        if (data != null)
          Positioned(
            left: 12,
            right: 12,
            bottom: 12,
            child: buildSummary(data),
          ),
      ],
    );
  }

  // builds the map screen
  Widget _buildMap(RouteData? data) {
    // if there is an error, then display this
    if (error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(30),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            spacing: 12,
            children: [
              Text(error!, textAlign: TextAlign.center),
              FilledButton(onPressed: retry, child: const Text('Try again')),
              TextButton(
                onPressed: changeRoute,
                child: const Text('Change route'),
              ),
            ],
          ),
        ),
      );
    }

    // waiting for data
    if (data == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return RouteMap(
      points: data.points,
      topInset: topInset,
      bottomInset: bottomInset,
      onNewRoute: changeRoute,
    );
  }

  // builds route info card
  Widget buildSummary(RouteData data) {
    final double miles = data.distMeters / 1609.344;
    final double minutes = (data.duration / 60).ceilToDouble();

    return Summary(
      context: context,
      miles: miles,
      minutes: minutes,
      data: data,
    );
  }
}

class Summary extends StatefulWidget {
  const Summary({
    super.key,
    required this.context,
    required this.miles,
    required this.minutes,
    required this.data,
  });

  final BuildContext context;
  final double miles;
  final double minutes;

  final RouteData data;

  @override
  State<Summary> createState() => _SummaryState();
}

class _SummaryState extends State<Summary> {
  bool minimized = true;

  // gets the ETA for route
  String getEta({required double minutes}) {
    final now = DateTime.now();
    final eta = now.add(Duration(minutes: minutes.toInt()));

    return eta.format('g:i');
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      elevation: 4,
      borderRadius: BorderRadius.circular(16),
      color: Theme.of(context).colorScheme.surface,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisSize: .min,
          spacing: 8,
          children: [
            Text(
              "ETA: ${getEta(minutes: widget.minutes)}",
              style: TextStyle(
                letterSpacing: 1,
                fontSize: 22,
                fontWeight: .bold,
              ),
            ),
            Row(
              mainAxisAlignment: .center,
              spacing: 20,
              children: [
                AccountStatBox(
                  labelText: "Distance (mi)",
                  statNumber: double.parse(widget.miles.toStringAsFixed(2)),
                  icon: Icons.directions_walk,
                  iconColor: Colors.green,
                ),
                AccountStatBox(
                  labelText: "Walk (min)",
                  statNumber: widget.minutes,
                  icon: Icons.timer,
                  iconColor: const Color.fromARGB(255, 232, 177, 40),
                ),
              ],
            ),
            Text(
              'Safety Score: ${widget.data.safetyScore}',
              style: TextStyle(
                letterSpacing: 1,
                fontSize: 15,
                fontWeight: .bold,
                color: Colors.blueGrey,
              ),
            ),
            WarningsWidget(warnings: widget.data.warnings.cast()),
          ],
        ),
      ),
    );
  }
}

class WarningsWidget extends StatelessWidget {
  final List<String> warnings;

  const WarningsWidget({super.key, required this.warnings});

  @override
  Widget build(BuildContext context) {
    return Visibility(
      visible: warnings.isNotEmpty,
      child: IconButton.filledTonal(
        style: ButtonStyle(),
        onPressed: () => showDialog(
          context: context,
          builder: (BuildContext context) => dialogBuild(context),
        ),
        icon: Icon(Icons.warning, color: Colors.deepOrange),
      ),
    );
  }

  Widget dialogBuild(BuildContext context) {
    // builds the content in the dialog
    final List<Widget> content = [];
    for (String w in warnings) {
      content.add(Text(w));
    }

    return AlertDialog(
      title: Text("Warnings"),
      icon: Icon(Icons.warning, size: 40, color: Colors.deepOrange),
      content: Column(
        mainAxisSize: .min,
        children: content,
      ), // doesn't allow ListView to be used
    );
  }
}
