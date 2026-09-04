class Farm {
  final int id;
  final String name;
  final String? location;
  final int ownerId;

  Farm({
    required this.id,
    required this.name,
    this.location,
    required this.ownerId,
  });

  factory Farm.fromJson(Map<String, dynamic> json) {
    return Farm(
      id: json['id'] as int,
      name: json['name'] as String,
      location: json['location'] as String?,
      ownerId: json['owner_id'] as int,
    );
  }
}
