ROUTEWISE INTEGRATED DEMO

1. Copy the RouteWise_Integrated folder into your Routewise-Research project root, next to data/ and results/.
2. In VS Code terminal at Routewise-Research run:
   .\.venv\Scripts\python.exe -m pip install fastapi uvicorn osmnx networkx joblib pandas numpy scikit-learn
3. Start the server:
   .\.venv\Scripts\python.exe -m uvicorn RouteWise_Integrated.server:app --reload
4. Open http://127.0.0.1:8000/ in your browser (NOT index.html directly).
5. Enter Times Square and Empire State Building; click Find Best Route.

Notes: Uses Manhattan road-network shortest-distance routing. ML estimate is experimental and uses placeholder weather and current computer clock. Safety/fuel/traffic ranking and route score are not implemented. Do not claim fastest-route optimization. Requires data/manhattan_drive.graphml and results/validated_model.joblib.
