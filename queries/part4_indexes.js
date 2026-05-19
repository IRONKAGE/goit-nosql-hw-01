use spotify;

print("\n--- Завдання 1. Аналіз запиту та індексація ---");

// Виносимо умови запиту в змінні, щоб не дублювати код (DRY)
const query = {
  track_genre: "pop",
  "audio_features.danceability": { $gte: 0.7 }
};
const sortOption = { popularity: -1 };

// 1. Аналіз ДО створення індексу
const explainBefore = db.tracks.find(query).sort(sortOption).explain("executionStats");
print("Час виконання БЕЗ індексу (мс):", explainBefore.executionStats.executionTimeMillis);
print("Досліджено документів (COLLSCAN):", explainBefore.executionStats.totalDocsExamined);

// 2. Створення індексу (Правило ESR: Equality, Sort, Range)
db.tracks.createIndex({
    track_genre: 1,
    popularity: -1,
    "audio_features.danceability": 1
});

// 3. Аналіз ПІСЛЯ створення індексу
const explainAfter = db.tracks.find(query).sort(sortOption).explain("executionStats");
print("Час виконання З індексом (мс):", explainAfter.executionStats.executionTimeMillis);
print("Досліджено документів (IXSCAN):", explainAfter.executionStats.totalDocsExamined);


print("\n--- Завдання 2. Індекс для інших полів (Фонова робота) ---");

// Складений індекс для оптимізації фонових треків
db.tracks.createIndex({
    explicit: 1,
    "audio_features.instrumentalness": 1,
    "audio_features.speechiness": 1
});

const explainBackground = db.tracks.find({
  "audio_features.instrumentalness": { $gt: 0.5 },
  "audio_features.speechiness": { $lt: 0.1 },
  explicit: false
}).explain("executionStats");

print("Використаний індекс для фонової музики:", explainBackground.queryPlanner.winningPlan.inputStage.indexName);
