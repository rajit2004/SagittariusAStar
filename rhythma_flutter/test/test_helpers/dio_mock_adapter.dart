import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'package:rhythma/services/api_client.dart';

class MockDioResponse {
  final int statusCode;
  final Map<String, dynamic>? data;

  final Map<String, List<String>>? headers;

  const MockDioResponse(this.statusCode, [this.data, this.headers]);
}

class MockDioAdapter implements HttpClientAdapter {
  MockDioAdapter(this._handler);

  final MockDioResponse Function(RequestOptions options) _handler;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final response = _handler(options);
    return ResponseBody.fromString(
      response.data != null ? jsonEncode(response.data) : '',
      response.statusCode,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
        ...?response.headers,
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void installMockDioAdapter(
  MockDioResponse Function(RequestOptions options) handler,
) {
  ApiClient.dio.httpClientAdapter = MockDioAdapter(handler);
}

void restoreDioAdapter() {
  ApiClient.dio.httpClientAdapter = IOHttpClientAdapter();
}
