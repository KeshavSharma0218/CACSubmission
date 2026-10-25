import 'dart:convert' as convert;

import 'package:flutter/foundation.dart' show debugPrint;
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

const String _apiBase = 'https://safewalk-backend-l7a7.onrender.com/api/v1';

/// Thrown when an address can't be turned into coordinates. [message] is
/// written to be shown to the user.
class GeocodeException implements Exception {
  GeocodeException(this.message);
  final String message;

  @override
  String toString() => message;
}

class MapDataFetch {
  /// Turns a street address into `{"lat": ..., "lon": ...}` using the API's
  /// geocode endpoint. Throws [GeocodeException] if the address isn't found.
  static Future<Map<String, double>> geocode(String address) async {
    final url = Uri.parse(
      '$_apiBase/geocode',
    ).replace(queryParameters: {'address': address});

    final response = await http.get(url).timeout(const Duration(seconds: 60));

    // could not find the address or address does not exist
    if (response.statusCode == 400 ||
        response.statusCode == 404 ||
        response.statusCode == 422) {
      throw GeocodeException('Could not find "$address".');
    }
    // handle other errors
    if (response.statusCode != 200) {
      throw Exception('Geocode error code: ${response.statusCode}');
    }

    // API output: {"coordinate": {"lat": ..., "lon": ...}, "address": "..."}
    final json = convert.jsonDecode(response.body);
    final coordinate = json is Map ? json['coordinate'] : null;
    final lat = coordinate is Map ? coordinate['lat'] : null;
    final lon = coordinate is Map ? coordinate['lon'] : null;

    if (lat is! num || lon is! num) {
      debugPrint('Unexpected geocode response: ${response.body}');
      throw GeocodeException('Could not find "$address".');
    }
    return {'lat': lat.toDouble(), 'lon': lon.toDouble()};
  }

  /// Requests the safest route between [startCoords] and [endCoords]
  /// (each `{"lat": ..., "lon": ...}`) and returns it as a [RouteData].
  static Future<RouteData> fetchRouteData(
    Map<String, double> startCoords,
    Map<String, double> endCoords,
  ) async {
    String baseUrl = '$_apiBase/route';
    Uri url = Uri.parse(baseUrl);

    var httpResponse = await http.post(
      url,
      headers: <String, String>{
        'Content-Type': 'application/json; charset=UTF-8',
      },
      body: convert.jsonEncode({
        "start": startCoords,
        "destination": endCoords,
        "preference": "safest",
        "require_sidewalk": false,
      }),
    );

    if (httpResponse.statusCode == 200) {
      final jsonResponse =
          convert.jsonDecode(httpResponse.body) as Map<String, dynamic>;
      return RouteData.fromJson(jsonResponse);
    } else {
      throw Exception("Error code: ${httpResponse.statusCode}");
    }
  }
}

// data for route after api call
class RouteData {
  final List<dynamic> coordinates;
  final double distMeters;
  final double duration; // seconds
  final double safetyScore;
  final List<dynamic> warnings;

  RouteData({
    required this.coordinates,
    required this.distMeters,
    required this.duration,
    required this.safetyScore,
    required this.warnings,
  });

  /// [coordinates] as map points. The API sends `{"lat": ..., "lon": ...}`.
  late final List<LatLng> points = [
    for (final c in coordinates)
      LatLng((c['lat'] as num).toDouble(), (c['lon'] as num).toDouble()),
  ];

  // `as num` then `toDouble()` because JSON gives an int for whole numbers
  // (e.g. 1800), which would throw if assigned straight to a double.
  factory RouteData.fromMap(Map<String, dynamic> json) {
    return RouteData(
      coordinates: json['coordinates'] as List<dynamic>,
      distMeters: (json['distance_m'] as num).toDouble(),
      duration: (json['duration_seconds'] as num).toDouble(),
      safetyScore: (json['safety_score'] as num).toDouble(),
      warnings: json['warnings'] as List<dynamic>,
    );
  }

  factory RouteData.fromJson(Map<dynamic, dynamic> json) {
    return RouteData(
      coordinates: json['coordinates'] as List<dynamic>,
      distMeters: (json['distance_m'] as num).toDouble(),
      duration: (json['estimated_walking_time_seconds'] as num).toDouble(),
      safetyScore: (json['safety_score'] as num).toDouble(),
      warnings: json['warnings'] as List<dynamic>,
    );
  }
}
