package ru.vexa.driver

fun main() {
    check(DriverDutyRules.canStartBreak(emptyList(), false))
    check(DriverDutyRules.canStartBreak(listOf("completed", "cancelled"), false))
    check(!DriverDutyRules.canStartBreak(emptyList(), true))
    check(!DriverDutyRules.canStartBreak(listOf("assigned"), false))
    check(!DriverDutyRules.canStartBreak(listOf("arrived"), false))
    check(!DriverDutyRules.canStartBreak(listOf("in_progress"), false))
    println("PASS: driver duty rules (6 cases)")
}
