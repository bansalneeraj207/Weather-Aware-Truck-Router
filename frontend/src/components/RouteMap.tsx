/** Trip route lines on an OpenFreeMap basemap. */

import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { GeoJSONSource } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { TripResult } from '../api/trips'
import {
  checkpointFeatureCollection,
  heatmapFeatureCollection,
  routeFeatureCollection,
  shownRoutes,
} from './routes'

interface RouteMapProps {
  trip: TripResult
  selectedRouteIndex: number
  forecastHour: number
  showForecastOverlay: boolean
}

const SELECTED_COLOR = '#2563eb'
const OTHER_COLOR = '#6b7280'
const SEVERITY_COLOR: unknown[] = [
  'match',
  ['get', 'severity'],
  'LOW',
  '#16a34a',
  'MODERATE',
  '#ca8a04',
  'HIGH',
  '#ea580c',
  'SEVERE',
  '#dc2626',
  'NO_TRAVEL',
  '#7f1d1d',
  '#9ca3af',
]

export function RouteMap({
  trip,
  selectedRouteIndex,
  forecastHour,
  showForecastOverlay,
}: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [ready, setReady] = useState(false)
  const [initialMapState] = useState(() => ({
    selectedRouteIndex,
    forecastHour,
    showForecastOverlay,
  }))

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const bounds = new maplibregl.LngLatBounds()
    bounds.extend([trip.start.lon, trip.start.lat])
    bounds.extend([trip.end.lon, trip.end.lat])
    for (const route of shownRoutes(trip.routes)) {
      for (const coord of route.geometry) {
        bounds.extend(coord)
      }
    }

    const map = new maplibregl.Map({
      container,
      style: 'https://tiles.openfreemap.org/styles/bright',
      center: [trip.start.lon, trip.start.lat],
      zoom: 5,
      attributionControl: { compact: true },
    })
    mapRef.current = map

    const onLoad = () => {
      map.addSource('heatmap', {
        type: 'geojson',
        data: heatmapFeatureCollection(
          trip,
          initialMapState.selectedRouteIndex,
          initialMapState.forecastHour,
        ),
      })
      map.addLayer({
        id: 'weather-heat',
        type: 'circle',
        source: 'heatmap',
        layout: { visibility: initialMapState.showForecastOverlay ? 'visible' : 'none' },
        paint: {
          'circle-radius': 28,
          'circle-blur': 0.85,
          'circle-opacity': 0.5,
          'circle-color': SEVERITY_COLOR as maplibregl.ExpressionSpecification,
        },
      })
      map.addSource('route', {
        type: 'geojson',
        data: routeFeatureCollection(trip.routes, initialMapState.selectedRouteIndex),
      })
      map.addLayer({
        id: 'route',
        type: 'line',
        source: 'route',
        layout: {
          'line-join': 'round',
          'line-cap': 'round',
        },
        paint: {
          'line-color': [
            'case',
            ['==', ['get', 'selected'], 1],
            SELECTED_COLOR,
            OTHER_COLOR,
          ],
          'line-width': ['case', ['==', ['get', 'selected'], 1], 6, 4],
        },
      })
      map.addSource('checkpoints', {
        type: 'geojson',
        data: checkpointFeatureCollection(trip, initialMapState.selectedRouteIndex),
      })
      map.addLayer({
        id: 'checkpoint',
        type: 'circle',
        source: 'checkpoints',
        paint: {
          'circle-radius': 6,
          'circle-color': SEVERITY_COLOR as maplibregl.ExpressionSpecification,
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#ffffff',
        },
      })
      map.on('click', 'checkpoint', (event) => {
        const feature = event.features?.[0]
        const properties = feature?.properties
        if (!event.lngLat || !properties) return
        const parts = [String(properties.eta_label), String(properties.severity)]
        if (properties.wind_mph != null) parts.push(`${properties.wind_mph} mph wind`)
        if (typeof properties.rain_in_hr === 'number') {
          parts.push(`${properties.rain_in_hr} in/hr rain`)
        }
        if (typeof properties.snow_in_hr === 'number') {
          parts.push(`${properties.snow_in_hr} in/hr snow`)
        }
        new maplibregl.Popup({ closeButton: false, offset: 12 })
          .setLngLat(event.lngLat)
          .setText(parts.join(' · '))
          .addTo(map)
      })
      map.on('mouseenter', 'checkpoint', () => {
        map.getCanvas().style.cursor = 'pointer'
      })
      map.on('mouseleave', 'checkpoint', () => {
        map.getCanvas().style.cursor = ''
      })
      map.resize()
      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 48, duration: 0 })
      }
      setReady(true)
    }

    map.on('load', onLoad)

    return () => {
      map.off('load', onLoad)
      map.remove()
      mapRef.current = null
      setReady(false)
    }
  }, [trip, initialMapState])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const routeSource = map.getSource('route') as GeoJSONSource | undefined
    routeSource?.setData(routeFeatureCollection(trip.routes, selectedRouteIndex))
    const checkpointSource = map.getSource('checkpoints') as GeoJSONSource | undefined
    checkpointSource?.setData(
      checkpointFeatureCollection(trip, selectedRouteIndex),
    )
    const heatmapSource = map.getSource('heatmap') as GeoJSONSource | undefined
    heatmapSource?.setData(
      heatmapFeatureCollection(trip, selectedRouteIndex, forecastHour),
    )
    map.setLayoutProperty(
      'weather-heat',
      'visibility',
      showForecastOverlay ? 'visible' : 'none',
    )
  }, [trip, selectedRouteIndex, forecastHour, showForecastOverlay, ready])

  return <div ref={containerRef} className="map-container" data-testid="route-map" />
}
