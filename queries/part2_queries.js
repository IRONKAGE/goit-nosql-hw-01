use spotify;

print("--- Завдання 1. Треки для вечірки ---");
const partyTracks = db.tracks.find(
  {
    "audio_features.danceability": { $gt: 0.7 },
    "audio_features.energy": { $gt: 0.7 },
    duration_ms: { $gte: 180000, $lte: 300000 }
  },
  {
    track_name: 1,
    artists: 1,
    duration_ms: 1,
    "audio_features.danceability": 1,
    _id: 0
  }
).limit(5).toArray(); // Ліміт для красивого виводу
printjson(partyTracks);

print("\n--- Завдання 2. Виконавці, у яких усі треки популярні ---");
const popularArtists = db.tracks.aggregate([
  { $unwind: "$artists" },
  {
    $group: {
      _id: "$artists",
      track_count: { $sum: 1 },
      min_popularity: { $min: "$popularity" },
      avg_popularity: { $avg: "$popularity" }
    }
  },
  {
    $match: {
      track_count: { $gte: 3 },
      min_popularity: { $gte: 60 }
    }
  },
  { $sort: { avg_popularity: -1 } },
  { $limit: 20 },
  {
    $project: {
      _id: 0,
      artist: "$_id",
      track_count: 1,
      min_popularity: 1,
      avg_popularity: { $round: ["$avg_popularity", 1] }
    }
  }
]).toArray();
printjson(popularArtists);

print("\n--- Завдання 3. Нетипові треки (Outliers - Window Functions) ---");
const outlierTracks = db.tracks.aggregate([
  {
    // Аналог OVER (PARTITION BY track_genre) в SQL.
    // Уникає BSON 16MB ліміту, бо не використовує $push: "$$ROOT"
    $setWindowFields: {
      partitionBy: "$track_genre",
      output: {
        avg_tempo: { $avg: "$audio_features.tempo" },
        std_tempo: { $stdDevPop: "$audio_features.tempo" }
      }
    }
  },
  {
    $addFields: {
      outlier_threshold: {
        $add: ["$avg_tempo", { $multiply: [2, "$std_tempo"] }]
      }
    }
  },
  {
    // Відсіюємо звичайні треки, залишаючи лише ті, що перевищують поріг
    $match: {
      $expr: { $gt: ["$audio_features.tempo", "$outlier_threshold"] }
    }
  },
  {
    // Тепер, коли їх залишилось мало (лише аутлаєри), можемо безпечно групувати
    $group: {
      _id: "$track_genre",
      avg_tempo: { $first: "$avg_tempo" },
      outlier_threshold: { $first: "$outlier_threshold" },
      outlier_tracks: {
        $push: {
          _id: "$_id",
          track_name: "$track_name",
          popularity: "$popularity",
          artists: "$artists",
          audio_features: { tempo: "$audio_features.tempo" }
        }
      }
    }
  },
  {
    $project: {
      _id: 0,
      genre: "$_id",
      avg_tempo: { $round: ["$avg_tempo", 2] },
      outlier_threshold: { $round: ["$outlier_threshold", 2] },
      outlier_tracks: 1
    }
  },
  { $limit: 2 } // Ліміт для демо, щоб не забивати консоль
]).toArray();
printjson(outlierTracks);

print("\n--- Завдання 4: Треки для фонової роботи ---");
const backgroundTracks = db.tracks.find(
  {
    "audio_features.loudness": { $lt: -10 },
    "audio_features.speechiness": { $lt: 0.1 },
    "audio_features.instrumentalness": { $gt: 0.5 },
    explicit: false
  },
  {
    track_name: 1,
    artists: 1,
    track_genre: 1,
    _id: 0
  }
).limit(5).toArray();
printjson(backgroundTracks);
