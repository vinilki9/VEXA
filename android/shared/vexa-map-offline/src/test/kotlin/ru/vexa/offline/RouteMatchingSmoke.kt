package ru.vexa.offline

fun main() {
    val route = listOf(NavPoint(55.7500, 37.6000), NavPoint(55.7510, 37.6000))
    val on = RouteMatcher.project(NavPoint(55.7505, 37.6000), route)!!
    check(on.deviationMeters < 1.0)
    val off = RouteMatcher.project(NavPoint(55.7505, 37.6020), route)!!
    check(off.deviationMeters > 100.0)
    check(RouteMatcher.project(NavPoint(Double.NaN, 37.6), route) == null)
    check(RouteMatcher.project(NavPoint(55.0, 37.0), emptyList()) == null)
    val gate = RerouteGate()
    check(!gate.observe(60.0, 1000, true))
    check(!gate.observe(60.0, 2000, true))
    check(gate.observe(60.0, 3000, true))
    check(!gate.observe(60.0, 4000, true))
    check(!gate.observe(60.0, 5000, true))
    check(!gate.observe(60.0, 6000, true)) // cooldown
    check(!gate.observe(10.0, 7000, true)) // back on route
    check(CameraMotion.bearing(359.0, 1.0, 0.5) < 1.0)
    val items = listOf(PickupCandidate("illegal", route[0], 10.0, 0.0, false, true),
        PickupCandidate("ok", route[0], 30.0, 10.0, true, true))
    check(PickupSafety.bestVerified(items)?.id == "ok")
    println("PASS: geometry, outlier reroute gate, camera, verified pickup")
}
