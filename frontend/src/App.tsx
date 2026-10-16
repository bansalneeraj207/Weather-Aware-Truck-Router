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
    </div>
  )
}

export default App
