import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

/// Interactive map that draws a walking route with start and end pins and
/// frames the whole route on load. Give it a bounded height (e.g. SizedBox).
class RouteMap extends StatefulWidget {
  const RouteMap({
    super.key,
    required this.points,
    this.topInset = 0,
    this.bottomInset = 0,
    this.onNewRoute,
  });

  final List<LatLng> points;

  /// Space at the top/bottom covered by widgets floating over the map. The
  /// route is framed, and the attribution and buttons placed, outside it.
  final double topInset;
  final double bottomInset;

  /// Called when the user taps the "New route" button. The button is hidden
  /// if this is null.
  final VoidCallback? onNewRoute;

  @override
  State<RouteMap> createState() => _RouteMapState();
}

class _RouteMapState extends State<RouteMap> {
  static const _routeColor = Color(0xFF1B7F5C);

  final _mapController = MapController();

  CameraFit get _fit => CameraFit.bounds(
    bounds: LatLngBounds.fromPoints(widget.points),
    padding: EdgeInsets.fromLTRB(
      48,
      48 + widget.topInset,
      48,
      48 + widget.bottomInset,
    ),
    maxZoom: 18, // stops a very short route from zooming in absurdly far
  );

  @override
  void didUpdateWidget(covariant RouteMap oldWidget) {
    super.didUpdateWidget(oldWidget);
    // A new route (e.g. after a new search) gets re-framed automatically.
    if (oldWidget.points != widget.points && widget.points.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _mapController.fitCamera(_fit);
      });
    }
  }

  @override
  void dispose() {
    _mapController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final points = widget.points;
    if (points.isEmpty) {
      return const Center(child: Text('No route to show.'));
    }

    return Stack(
      children: [
        FlutterMap(
          mapController: _mapController,
          options: MapOptions(
            initialCameraFit: _fit,
            // Pan, pinch-zoom and double-tap zoom. Rotation is off because this
            // map sits inside a scrolling page; remove the `& ~rotate` to allow it.
            interactionOptions: const InteractionOptions(
              flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
            ),
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName:
                  'com.example.flutter_proj', // needs to be set or else map tiles will be blocked
              // caching system for map tiles. Allows app to use already loaded tiles from cache.
              // we prolly don't need this rn, but i think its nice to have
              // the cache isn't configured to clear tho so if it causes problems then we can just comment this out later
              tileProvider: NetworkTileProvider(
                cachingProvider: BuiltInMapCachingProvider.getOrCreateInstance(
                  maxCacheSize: 1_000_000_000,
                ),
              ),
            ),
            // route line
            PolylineLayer(
              polylines: [
                Polyline(
                  points: points,
                  strokeWidth: 6,
                  color: _routeColor,
                  borderStrokeWidth: 3,
                  borderColor: Colors.white,
                  strokeCap: StrokeCap.round,
                  strokeJoin: StrokeJoin.round,
                ),
              ],
            ),
            // marking points
            MarkerLayer(
              markers: [
                _pin(points.first, const Color(0xFF2E7D32)),
                _pin(points.last, const Color(0xFFC62828)),
              ],
            ),
          ],
        ),
        Positioned(
          top: 8 + widget.topInset,
          right: 8,
          child: Column(
            spacing: 8,
            children: [
              // button to create a new route
              if (widget.onNewRoute != null)
                IconButton.filledTonal(
                  tooltip: 'New route',
                  onPressed: widget.onNewRoute,
                  icon: const Icon(Icons.add),
                ),
              // zooms to show full route
              IconButton.filledTonal(
                tooltip: 'Show full route',
                onPressed: () => _mapController.fitCamera(_fit),
                icon: const Icon(Icons.zoom_out_map),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Marker _pin(LatLng point, Color color) => Marker(
    point: point,
    width: 44,
    height: 44,
    // Puts the bottom tip of the pin on the coordinate.
    alignment: Alignment.topCenter,
    child: Icon(Icons.location_on, size: 44, color: color),
  );
}
