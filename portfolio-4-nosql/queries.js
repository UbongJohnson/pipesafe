// =====================================================================
// MIT 8103 Portfolio 4 - NoSQL and Advanced Data Models
// queries.js : MongoDB queries on the PipeSafe document model
// Run in mongosh (or the Atlas Data Explorer shell):
//   mongosh "mongodb+srv://cluster0.xxxxx.mongodb.net/pipesafe" --username USER queries.js
// The same queries are in scripts/run_queries.py.
// =====================================================================
db = db.getSiblingDB("pipesafe");

// N1. Complete record of one accident in ONE read (relational: about 11 tables joined)
printjson(db.accidents.findOne({ _id: 20170094 }, { narrative: 0 }));

// N2. External corrosion with no cathodic protection, by state (Portfolio 2 Q7)
printjson(db.accidents.aggregate([
  { $match: { "cause.detail": "EXTERNAL CORROSION",
              "cause.answers.under_cathodic_protection_ind": false } },
  { $group: { _id: "$location.state", accidents: { $sum: 1 } } },
  { $sort: { accidents: -1, _id: 1 } }
]).toArray());

// N3. Accidents, barrels released and total cost by cause category
printjson(db.accidents.aggregate([
  { $group: { _id: "$cause.category",
              accidents: { $sum: 1 },
              bbl_released: { $sum: "$release.unintentional_bbls" },
              total_cost_usd: { $sum: "$total_cost_usd" } } },
  { $sort: { total_cost_usd: -1 } }
]).toArray());

// N4. Fatalities and injuries by person group ($unwind the embedded array)
printjson(db.accidents.aggregate([
  { $unwind: "$casualties" },
  { $group: { _id: "$casualties.group",
              accidents: { $sum: 1 },
              fatalities: { $sum: "$casualties.fatalities" },
              injuries: { $sum: "$casualties.injuries" } } },
  { $sort: { fatalities: -1, injuries: -1 } }
]).toArray());

// N5. Flexible schema: a field that exists in only a few documents
printjson(db.accidents.aggregate([
  { $match: { "cause.answers.vehicle_type": { $exists: true } } },
  { $group: { _id: "$cause.answers.vehicle_type", accidents: { $sum: 1 } } },
  { $sort: { accidents: -1 } }
]).toArray());

// N6. How many different cause questions each category uses
printjson(db.accidents.aggregate([
  { $project: { category: "$cause.category", fields: { $objectToArray: "$cause.answers" } } },
  { $unwind: "$fields" },
  { $group: { _id: { category: "$category", field: "$fields.k" } } },
  { $group: { _id: "$_id.category", distinct_fields: { $sum: 1 } } },
  { $sort: { distinct_fields: -1 } }
]).toArray());

// N7. Five most recent accidents for one operator (uses the operator + date index)
printjson(db.accidents.find(
  { "operator.id": 31684 },
  { accident_datetime: 1, "report.type": 1, "release.unintentional_bbls": 1 }
).sort({ accident_datetime: -1 }).limit(5).toArray());
// Check the index is used: look for "IXSCAN" in the winning plan
printjson(db.accidents.find({ "operator.id": 31684 })
  .sort({ accident_datetime: -1 }).explain("executionStats").queryPlanner.winningPlan);

// N8. Operators reported under more than one name
printjson(db.operators.find(
  { "name_history.1": { $exists: true } },
  { name: 1, name_history: 1 }
).sort({ _id: 1 }).limit(5).toArray());

// N9. Narratives mentioning frozen equipment (Portfolio 2 Q6 returned 36)
print(db.accidents.countDocuments({ narrative: { $regex: "frozen", $options: "i" } }));

// N10. Accidents within 25 km of Cushing, Oklahoma (needs the 2dsphere index)
// Expected answer: 178 (checked independently with the haversine formula)
print(db.accidents.countDocuments({
  "location.geo": { $geoWithin: { $centerSphere: [[-96.7670, 35.9851], 25 / 6378.1] } }
}));
