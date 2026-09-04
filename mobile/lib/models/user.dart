class AuthToken {
  final String accessToken;
  final int expiresIn;

  AuthToken({required this.accessToken, required this.expiresIn});

  factory AuthToken.fromJson(Map<String, dynamic> json) {
    return AuthToken(
      accessToken: json['access_token'] as String,
      expiresIn: json['expires_in'] as int,
    );
  }
}
