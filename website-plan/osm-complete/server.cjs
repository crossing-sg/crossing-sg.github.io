/* Isolated loopback preview using the all-highways release and in-memory Sheets. */
const fs=require('node:fs'),path=require('node:path');
process.env.QA_ROAD_DATA_DIR='website/data/osm-complete/proposal-roads';
process.env.QA_ROAD_FIXTURES=path.join(__dirname,'fixtures.json');
process.env.QA_ROAD_VERSION=JSON.parse(fs.readFileSync(path.join(__dirname,'../../',process.env.QA_ROAD_DATA_DIR,'manifest.json'))).version;
require('../road-conflation/integration_server.cjs');
