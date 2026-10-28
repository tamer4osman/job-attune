# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
#
# Use as a subdirectory:
#   add_subdirectory(omnidecide-c)
#   target_link_libraries(my_app PRIVATE omnidecide::omnidecide)

cmake_minimum_required(VERSION 3.10)
project(omnidecide VERSION 1.0.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

option(OMNIDECIDE_BUILD_EXAMPLES "Build the example programs" ${PROJECT_IS_TOP_LEVEL})
option(OMNIDECIDE_BUILD_TESTS "Build and register the smoke test" ${PROJECT_IS_TOP_LEVEL})

file(GLOB ODK_SOURCES CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/src/*.c)

add_library(omnidecide ${ODK_SOURCES})
add_library(omnidecide::omnidecide ALIAS omnidecide)

target_include_directories(omnidecide
    PUBLIC  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:include>
    PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)

# Disabling floating-point contraction keeps results bit-identical across
# compilers, optimization levels and machines.
if(NOT MSVC)
    target_compile_options(omnidecide PRIVATE -ffp-contract=off)
endif()

find_library(ODK_MATH_LIBRARY m)
if(ODK_MATH_LIBRARY)
    target_link_libraries(omnidecide PUBLIC ${ODK_MATH_LIBRARY})
endif()

if(OMNIDECIDE_BUILD_EXAMPLES)
    foreach(example odk_demo quickstart languages learning long_context explain model)
        add_executable(${example} examples/${example}.c)
        target_link_libraries(${example} PRIVATE omnidecide)
    endforeach()
endif()

if(OMNIDECIDE_BUILD_TESTS)
    enable_testing()
    add_executable(smoke_test tests/smoke_test.c)
    target_link_libraries(smoke_test PRIVATE omnidecide)
    add_test(NAME smoke_test COMMAND smoke_test
             WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
endif()

install(TARGETS omnidecide ARCHIVE DESTINATION lib)
install(FILES include/omnidecide.h DESTINATION include)
