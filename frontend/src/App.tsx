import './App.css'
import TripPlanner from './components/TripPlanner'

function App() {
  return (
    <div>
      <h1>Truck Route Planner</h1>
      <p>
        Enter an origin, destination, departure time, and load. The app compares
        truck routes using the forecast at each checkpoint's arrival, then
        suggests the lowest weather-risk option.
      </p>
      <TripPlanner />
      <p className="provider-credits">
        Weather data by <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a>
        {' · '}Geocoding and road data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>
        {' · '}Routing by <a href="https://valhalla.github.io/valhalla/" target="_blank" rel="noreferrer">Valhalla</a>
      </p>
    </div>
  )
}

export default App
