// Перемикаємось на потрібну базу
use spotify;

// 1. Перед трансформацією видаляємо стару колекцію tracks, якщо вона існує (Ідемпотентність)
db.tracks.drop();

print("Починаємо трансформацію даних...");

// Виконуємо Aggregation Pipeline для зміни схеми
db.tracks_raw.aggregate([
  {
    // 3. Перетворення артистів та 4. Формування аудіо-характеристик
    $addFields: {
      artists: {
        $map: {
          input: { $split: ["$artists", ";"] },
          as: "artist",
          in: { $trim: { input: "$$artist" } }
        }
      },
      audio_features: {
        danceability: "$danceability",
        energy: "$energy",
        loudness: "$loudness",
        speechiness: "$speechiness",
        acousticness: "$acousticness",
        instrumentalness: "$instrumentalness",
        liveness: "$liveness",
        valence: "$valence",
        tempo: "$tempo",
        key: "$key",
        mode: "$mode",
        time_signature: "$time_signature"
      },
      duration_sec: { $round: [{ $divide: ["$duration_ms", 1000] }, 1] },
      popularity_tier: {
        $switch: {
          branches: [
            { case: { $gte: ["$popularity", 70] }, then: "high" },
            { case: { $lt: ["$popularity", 40] }, then: "low" }
          ],
          default: "medium"
        }
      }
    }
  },
  {
    // 2. Проекція полів (залишаємо лише необхідне) та 5. Очищення зайвих полів
    $project: {
      _id: 0, // Генеруємо нові ObjectIDs для tracks
      track_id: 1,
      track_name: 1,
      album_name: 1,
      explicit: 1,
      popularity: 1,
      duration_ms: 1,
      track_genre: 1,
      artists: 1,
      audio_features: 1,
      duration_sec: 1,
      popularity_tier: 1
    }
  },
  {
    // 6. Збереження результату в нову колекцію
    $out: "tracks"
  }
]);

// 7. Перевірка результату
const count = db.tracks.countDocuments();
print(`\n✅ Трансформація завершена. Кількість документів у колекції tracks: ${count}`);
print("\nПриклад трансформованого документа:");
printjson(db.tracks.findOne());
