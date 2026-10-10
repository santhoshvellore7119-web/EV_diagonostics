cmake_minimum_required(VERSION 3.10)
project(gazebo_battery_thermal_plugin)

find_package(gazebo REQUIRED)
include_directories(${GAZEBO_INCLUDE_DIRS})
link_directories(${GAZEBO_LIBRARY_DIRS})
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${GAZEBO_CXX_FLAGS} -std=c++17")

add_library(gazebo_battery_thermal_plugin SHARED gazebo_battery_thermal_plugin.cpp)
target_link_libraries(gazebo_battery_thermal_plugin ${GAZEBO_LIBRARIES})
