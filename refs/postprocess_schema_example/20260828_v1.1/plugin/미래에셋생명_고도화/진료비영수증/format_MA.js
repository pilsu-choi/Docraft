// const {Logger}            = require('common/logger');
const { Logger } = require('/usr/src/app/dist/apps/extn/libs/common/src/logger');

const { relative } = require("node:path");

const pluginUtilCache = require.resolve("./pluginUtil_MA.js");
delete require.cache[pluginUtilCache];
const pluginUtil = require(pluginUtilCache);

/**
 * 2024.09.23 루나
 * 조건 1. 추출 된 결과가 없는 경우(data.values === []) label 을 null 로 정의한다.
 */

let IPF_HGRK_EXTC_ITM_NO = 0; //입원료 상위항목레벨번호
let DNF_HGRK_EXTC_ITM_NO = 0; //투약및제재료 상위항목레벨번호
let INF_HGRK_EXTC_ITM_NO = 0; //주사료 상위항목레벨번호

exports.setResultFormat = function setResultFormat(
  values,
  keyObj,
  arrtcd,
  category
) {
  let resultArr = [];
  let extrtId = 1;
  let extc_itm_no = 1;

  // 진료비영수증의 표데이터 추출레벨번호 처리를 위해 작성
  let chartLvlNo = 0;
  let rlChartYN = false; // TODO 한 문서에 relativeLabelsInfo, relativeValueKeywordInfo 둘 다 사용하는 경우가 생기면 추가 작업 필요

  // 영역 추출 결과
  let areaSearchResult = values?.filter(
    (value) => value?.ruleName === "AreaSearch"
  );

  // values 에서 불필요한 값 제거
  values = values?.filter(
    (value) =>
      value?.ruleName !== "CollectTabularData" &&
      value?.ruleName !== "CollectStrikeThroughData" &&
      value?.ruleName !== "AreaSearch"
  );

  // 스키마에는 정의되어 있으나, 항목리스트.json 에는 정의되지 않은 경우에 대한 처리 (항목리스트.json 에 추가처리여부 정의)
  // 항목리스트 추출항목에 정의 된 항목이 없는 경우
  let afterItmYN = keyObj["추가처리여부"];
  if (afterItmYN === "Y" || keyObj["추출항목"]?.length < 1) {
    values
      ?.filter((value) => keyObj["추출항목"]?.indexOf(value?.name) < 0)
      .forEach((value) => {
        // 추출항목 마지막에 추가
        keyObj["추출항목"].push(value?.name);
      });

    // 표대상항목 중 항목리스트 표추출항목에 정의 된 항목이 없는 경우
    values
      ?.filter((value) => keyObj["표대상항목"]?.indexOf(value?.name) >= 0)
      .forEach((value) => {
        value?.data?.forEach((data) => {
          data?.values
            .filter((v) => {
              return v?.relativeLabelsInfo?.length > 0 ? true : false;
            })
            .forEach((v) => {
              if (v?.relativeLabelsInfo?.length > 0) {
                rlChartYN = true;
                //진료비영수증은 항목리스트에 정해진것만 추출하게하기
                // if (category == "진료비영수증") {
                //   v?.relativeLabelsInfo?.forEach((rl) => {
                //      if(keyObj["표추출제외항목"]?.indexOf(rl?.label) < 0 && keyObj["표추출항목"]?.indexOf(rl?.label) < 0)
                //      keyObj["표추출항목"]?.push(rl?.label);
                //   });
                // }
              }
            });
        });
      });
    
    keyObj["추출항목"] = keyObj["추출항목"]?.filter((key) => key !== "");
  }

  // 후처리항목이 있는 경우 표추출항목의 순서 변경되도록 설정
  keyObj["표추출항목"] = keyObj["표추출항목"]?.sort((a, b) => {
    return keyObj["후처리항목"]?.indexOf(a) - keyObj["후처리항목"]?.indexOf(b);
  });

  // resultArr push 로직 시작
  if (typeof values !== "undefined" && values?.length > 0) {
    keyObj["추출항목"]?.forEach((key, i) => {
      let itmValue = values?.filter(
        (value) => value?.name === key && value?.data?.length > 0
      );

      if (itmValue?.length < 1) {
        resultArr.push(
          resultFormat(
            keyObj,
            extrtId,
            extc_itm_no,
            1,
            null,
            key,
            null,
            null,
            [],
            [],
            1.0,
            "N",
            null
          )
        );
      } else {

        

        itmValue?.forEach((value) => {
          // 여러 번 출력 된 경우 status 가 0 아래 값 제거 후 label 합치기
          if (value?.data?.length > 1) {
            // [2025-04-16] status가 -1인 값(keyword 미추출)만 제거
            // [2026-01-18] status가 -3인 값(keyword 미추출)만 제거
            // value.data = value?.data?.filter((data) => data?.status >= 0 && !value?.selectRuleType?.includes("Check"));
            value.data = value?.data?.filter(
              (data) =>
                // (data?.status !== -1 && !value?.selectRuleType?.includes("Check")) ||
                // (data?.status !== -3 && !value?.selectRuleType?.includes("Check"))
                data?.status == 0
            );
          }

          // data 가 여러 개인 경우 (이미지 상 동일 키워드가 여러 번 나오는 경우)
          // 조건1. 첫 번째 값만 가져오는 것으로 처리
          // 조건2. SearchByKeyword 한정
          if (!keyObj["표대상항목"].includes(value?.name) && value.data?.length > 1) {
            value.data = [value?.data[0]];
          }

          // [2025-03-11] value?.data에 값이 없는 경우 처리
          if (value?.data?.length === 0) {
            resultArr.push(
              resultFormat(
                keyObj,
                extrtId,
                extc_itm_no,
                1,
                null,
                key,
                null,
                null,
                [],
                [],
                1.0,
                "N",
                null
              )
            );
          }

          value?.data?.forEach((data) => {
            // 표데이터
            if (keyObj["표대상항목"]?.indexOf(value?.name) >= 0) {

              // relativeLabelsInfo 를 사용하는 경우 (ex. 진료비영수증)
              if (rlChartYN) {
                if (keyObj["표대상항목"]?.indexOf(value?.name) === 0)
                  chartLvlNo = extc_itm_no;
                else extc_itm_no = chartLvlNo;

                keyObj["표추출항목"]?.forEach((k, kIdx) => {

                  let chartValue = data?.values?.filter((v) => {
                    let tmpLabel = "";
                    v?.relativeLabelsInfo?.forEach((rl) => {
                      tmpLabel += rl?.label;
                    });
                    if (k === tmpLabel) {
                      return true;
                    }
                  });

                  // TCD 테두리 모델에 의해서 중복된 항목에 대해서 여러 행이 나왔을 경우
                  if(chartValue?.length > 1) {

                    // if(k == "초음파진단료") console.log(`\n:: chartValue before :: \n${JSON.stringify(chartValue)}`);
                    // // if(k == "초음파진단료") console.log(`\n:: itmValue :: \n${JSON.stringify(itmValue)}`);
                    // if(k == "초음파진단료") console.log(`\n:: prevIndexArr :: \n${JSON.stringify(prevIndexArr)}`);
                    
                    if(new Set(chartValue.map(v => v?.relativeLabelsInfo?.[0].index)).size != chartValue.map(v => v?.relativeLabelsInfo?.[0].index).length) {

                      const result = [];

                      for (const group of chartValue) {

                        // 값이 있는 것 중 제일 첫 번째를 선택
                        if (group.label.length > 0 && result.length != 0) result.push(group);
                      }

                      chartValue = result.length != 0 ? result : chartValue[0] ?? [];
                    }
                  }

                  if (chartValue?.length > 0) {

                    chartValue?.forEach((o, idx) => {

                      // [2026.01.14] leftLabel 값 추가
                      o?.relativeLabelsInfo?.forEach((rl) => {

                        const leftIndex = pluginUtil.getArrtcdLowArr(
                            arrtcd,
                            null,
                            rl?.index,
                            "left"
                        )[0]?.index;

                        const leftLabel = pluginUtil.setArrtcdLabel(
                          pluginUtil.getArrtcdIdxValue(
                            arrtcd,
                            leftIndex
                        ));
                        
                        // 필수항목으로 들어오는 케이스는 "기본항목"으로 대체
                        if(leftLabel == "필수항목") {
                          rl.extc_itm_tpvl = "기본항목"
                        } else if(leftLabel === undefined || leftLabel === 'undefined') {

                          const bottomLabel = pluginUtil.setArrtcdLabel(
                            pluginUtil.getArrtcdIdxValue(
                              arrtcd,
                              pluginUtil.getArrtcdLowArr(
                                arrtcd,
                                null,
                                leftIndex,
                                "bottom"
                              )[0]?.index
                            )
                          );

                          if(bottomLabel == "선택항목") {
                            rl.extc_itm_tpvl = "기본항목";
                          } else {
                            rl.extc_itm_tpvl = null;
                          }

                        } else {
                          rl.extc_itm_tpvl = leftLabel;
                        }

                        let dupItms = ["1인실", "2·3인실", "4인실이상", "투약및조제료-행위료", "투약및조제료-약품비", "주사료-행위료", "주사료-약품비"];

                        if (dupItms?.indexOf(rl?.label) >= 0) {

                          let leftIndex = pluginUtil.getArrtcdLowArr(arrtcd, null, rl?.index, "left")[0]?.index;

                          // 상위레벨항목이 기본항목 또는 선택항목이 아닐 때
                          if(!["기본항목", "선택항목"].includes(rl.extc_itm_tpvl)) {

                            const moreLeftIndex = pluginUtil.getArrtcdLowArr(
                              arrtcd,
                              null,
                              leftIndex,
                              "left"
                            )?.[0]?.index ?? null;

                            const moreLeftLabel = pluginUtil.setArrtcdLabel(
                              pluginUtil.getArrtcdIdxValue(
                                arrtcd,
                                moreLeftIndex
                              )
                            );

                            // 옆 TCD만 존재할 때 체크
                            if(moreLeftLabel === undefined || moreLeftLabel === 'undefined') {

                              const bottomLabel = pluginUtil.setArrtcdLabel(
                                pluginUtil.getArrtcdIdxValue(
                                  arrtcd,
                                  pluginUtil.getArrtcdLowArr(
                                    arrtcd,
                                    null,
                                    moreLeftIndex,
                                    "bottom"
                                  )[0]?.index
                                )
                              );

                              if(bottomLabel == "선택항목") {
                                rl.extc_itm_tpvl = "기본항목";
                              } else {
                                rl.extc_itm_tpvl = null;
                              }

                            } else {
                              rl.extc_rst_cont09 = rl.extc_itm_tpvl;
                              rl.extc_itm_tpvl = moreLeftLabel;
                            }
                          }
                          rl.extc_rst_cont09 = leftLabel;
                        }
                      });
                    });

                    chartValue?.forEach((v) => {
                      v?.relativeLabelsInfo?.forEach((rl, rlIdx) => {

                        if (
                            rl?.label.includes("행위료") || rl?.label.includes("약품비") ||
                            (rl?.label.includes("기타") && !rl?.label.includes("기타치료"))
                          ) {
                          const [extc_rst_cont09, label] = rl?.label.split("-");
                          k = label;
                          if(!rl?.label.includes("기타")) {
                            rl.extc_rst_cont09 = extc_rst_cont09;
                          }
                        }

                        if(rl?.label == '입원료' && rl?.extc_rst_cont09 == null) IPF_HGRK_EXTC_ITM_NO = extc_itm_no;
                        if(rl?.label == '투약및제재료'&& rl?.extc_rst_cont09 == null) DNF_HGRK_EXTC_ITM_NO = extc_itm_no;
                        if(rl?.label == '주사료'&& rl?.extc_rst_cont09 == null) INF_HGRK_EXTC_ITM_NO = extc_itm_no;

                        rl.extc_rst_cont09 = ["1인실", "2·3인실", "4인실이상"].includes(rl?.label) ? "입원료" : rl?.extc_rst_cont09 || null;

                        // [테이블 내 금액부 해당] 일반문자로 읽은 ocr 숫자처리
                        // 숫자, 소수점 제외 탈락처리
                        v.label = v?.label
                                    .replace(/[Il\/]/g, "1")
                                    .replace(/[Oo]/g, "0")
                                    .replace(/B/g, "8")
                                    .replace(/b/g, "6")
                                    .replace(/[^0-9\-]/g, "");

                        v.label = v.label === "" ? "" : Number(v.label).toString();

                        if (rl?.label == '초음파진단료') console.log(`초음파진단료 extc_itm_no:: ${extc_itm_no}`);

                        resultArr.push(
                          resultFormat(
                            keyObj,
                            extrtId,
                            extc_itm_no,
                            keyObj["표타이틀"]?.indexOf(value?.name) + 1,
                            null,
                            k,
                            rl?.label,
                            v?.label,
                            rl?.coordinates,
                            v?.coordinates,
                            v?.confidence,
                            "Y",
                            value?.name,
                            rl?.extc_itm_tpvl,
                            rl?.extc_rst_cont09,
                            "table-contents",
                            rl?.index,
                            rl?.relativeLabelsInfo?.[0].index,
                          )
                        );

                        extrtId++;
                        extc_itm_no++;
                      });
                    });
                  }

                  // else if(k =="입원료" || k == "투약및조제료" || k == "주사료" || k == "합계") {
                  else {

                    let extc_rst_cont09 = "";

                    if (
                        k?.includes("행위료") || k?.includes("약품비") ||
                        ((k?.includes("기타") && !k?.includes("기타치료")) && k?.includes("-") &&
                        !k?.includes("기타1") && !k?.includes("기타2") && !k?.includes("기타3") && !k?.includes("기타4") && !k?.includes("기타5"))
                      ) {
                      const [extc_09, label] = k.split("-");
                      extc_rst_cont09 = extc_09;
                      k = label;
                      if(!k.includes("기타")) {
                        extc_rst_cont09 = extc_09;
                      }
                    }

                    if(k == '입원료') IPF_HGRK_EXTC_ITM_NO = extc_itm_no;
                    if(k == '투약및조제료') DNF_HGRK_EXTC_ITM_NO = extc_itm_no;
                    if(k == '주사료') INF_HGRK_EXTC_ITM_NO = extc_itm_no;

                    extc_rst_cont09 = ["1인실", "2·3인실", "4인실이상"].includes(k) ? "입원료" : extc_rst_cont09 || null;

                    resultArr.push(
                      resultFormat(
                        keyObj,
                        extrtId,
                        extc_itm_no,
                        keyObj["표타이틀"]?.indexOf(value?.name) + 1,
                        null,
                        k,
                        k,
                        null,
                        [],
                        [],
                        1.0,
                        "N",
                        value?.name,
                        null,
                        extc_rst_cont09,
                        "table-contents",
                        null,
                        null
                      )
                    );

                    extrtId++;
                    extc_itm_no++;
                  } 

                });
              }
              // relativeValueKeywordInfo 를 사용하는 경우 (ex. 진료비세부내역서)
              else {
                let chartTitle = keyObj["표타이틀"];
                if (
                  chartTitle.length < 1 &&
                  keyObj[`표타이틀_` + key]?.length > 0
                ) {
                  chartTitle = keyObj[`표타이틀_` + key];
                }

                data?.values?.forEach((v) => {
                  v?.relativeValueInfo?.forEach((r) => {});
                  let extrtSno = 0;
                  let valueSno = 0;

                  if (afterItmYN === "Y") {
                    chartTitle?.forEach((tv, ti) => {
                      extrtSno++;

                      // 추출 정의 항목과 추출된 key가 같은 경우 정의된 룰대로 push
                      if (
                        tv ===
                        v?.relativeValueInfo[valueSno]?.keyLabels?.join("_")
                      ) {
                        resultArr.push(
                          resultFormat(
                            keyObj,
                            extrtId,
                            extc_itm_no,
                            extrtSno,
                            null,
                            v?.relativeValueInfo[valueSno]?.keyLabels?.join(""),
                            v?.relativeValueInfo[valueSno]?.keyLabels?.join(""),
                            v?.relativeValueInfo[valueSno]?.label,
                            v?.relativeValueInfo[valueSno]?.coordinates,
                            v?.coordinates,
                            v?.relativeValueInfo[valueSno]?.confidence,
                            "Y",
                            value?.name
                          )
                        );
                        valueSno++;
                        // 추출 정의 항목과 추출된 key가 같지 않은 경우
                      } else {
                        // 메인 key로 뽑은 경우
                        if (tv === data?.keyLabels?.join("")) {
                          resultArr.push(
                            resultFormat(
                              keyObj,
                              extrtId,
                              extc_itm_no,
                              extrtSno,
                              null,
                              tv,
                              tv,
                              v?.label,
                              v?.coordinates,
                              v?.coordinates,
                              v?.confidence,
                              "Y",
                              value?.name
                            )
                          );
                          // 추출되지 않은 경우 'N'으로 PUSH
                        } else {
                          resultArr.push(
                            resultFormat(
                              keyObj,
                              extrtId,
                              extc_itm_no,
                              extrtSno,
                              null,
                              tv,
                              tv,
                              null,
                              [],
                              [],
                              1.0,
                              "N",
                              value?.name
                            )
                          );
                        }
                      }
                    });
                  } else {
                    // relativeValueKeywordInfo 로 정의 된 룰에 의한 추출 값
                    v?.relativeValueInfo?.forEach((rv) => {
                      extrtSno++;
                      resultArr.push(
                        resultFormat(
                          keyObj,
                          extrtId,
                          extc_itm_no,
                          extrtSno,
                          null,
                          rv?.keyLabels?.join(""),
                          rv?.keyLabels?.join(""),
                          rv?.label,
                          rv?.coordinates,
                          v?.coordinates,
                          rv?.confidence,
                          "Y",
                          value?.name
                        )
                      );
                    });
                  }

                  extrtId++;
                  extc_itm_no++;
                });
              }
            }
            // 추출 된 결과가 없는 경우
            else if (data?.values?.length < 1) {
              // resultArr.push(resultFormat(keyObj, extrtId, extc_itm_no, 0, null, value?.name, data?.keyLabels?.join(''), null, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "N", null));

              // [2025-04-15] status -1 은 'N' 처리
              if (data?.status === -1) {
                resultArr.push(
                  resultFormat(
                    keyObj,
                    extrtId,
                    extc_itm_no,
                    1,
                    null,
                    value?.name,
                    data?.keyLabels?.join(""),
                    null,
                    data?.values[0]?.coordinates,
                    [],
                    data?.values[0]?.confidence,
                    "N",
                    null
                  )
                );
              } else {
                // [2025-04-13] value?.data에 값이 없는 경우 'Y' 처리 (keyword만 추출, 값은 없는 경우)
                resultArr.push(
                  resultFormat(
                    keyObj,
                    extrtId,
                    extc_itm_no,
                    1,
                    null,
                    value?.name,
                    data?.keyLabels?.join(""),
                    null,
                    data?.values[0]?.coordinates,
                    [],
                    data?.values[0]?.confidence,
                    "Y",
                    null
                  )
                );
              }
            }
            // 한 가지 항목만 추출 된 경우
            else if (
              data?.values?.length > 0 &&
              data?.values[0]?.relativeLabelsInfo?.length < 1 &&
              data?.values[0]?.relativeValueInfo?.length < 1
            ) {

              let label = "";
              if (data?.values?.length > 1) {
                // [2025-04-20/NH생명] '병명' 또는 '병명코드' => 줄바꿈 시 '/' 추가
                if (value?.name?.includes("병명")) {
                  data?.values?.forEach((v, i) => {
                    if (i > 0) label = label + "/" + v?.label;
                    else label += v?.label;
                  });
                } else if (
                  value?.name?.includes("소견") ||
                  value?.name?.includes("주소") ||
                  value?.name?.includes("상호") ||
                  value?.name?.includes("소재지")
                ) {
                  data?.values?.forEach((v, i) => {
                    if (i > 0) label = label + " " + v?.label;
                    else label += v?.label;
                  });
                } else {
                  data?.values?.forEach((v) => (label += v?.label));
                }
              } else {
                if (
                  value?.name?.includes("소견") ||
                  value?.name?.includes("주소") ||
                  value?.name?.includes("상호") ||
                  value?.name?.includes("소재지")
                ) {
                  // 범용 모델 추출 결과
                  if (data?.values[0]?.ocrInfo !== undefined) {
                    data?.values[0]?.ocrInfo?.forEach((ocr, i) => {
                      if (i > 0) label = label + " " + ocr?.label;
                      else label += ocr?.label;
                    });
                    // 정보 추출 모델 추출 결과
                  } else {
                    if (data?.values[0]?.entity_info !== undefined) {
                      data?.values[0]?.entity_info[0]?.ocrs?.forEach(
                        (ocr, i) => {
                          if (i > 0) label = label + " " + ocr?.label;
                          else label += ocr?.label;
                        }
                      );
                    }
                  }
                } else label = data?.values[0]?.label;
              }
              // [2025-04-20/NH생명] '치료내용 ~' 또는 '주소' => 공백 포함
              // if(value?.name?.includes("소견")) {
              //   if(data?value?.lengt)
              // }
              resultArr.push(
                resultFormat(
                  keyObj,
                  extrtId,
                  extc_itm_no,
                  1,
                  null,
                  value?.name,
                  data?.keyLabels?.join(""),
                  label,
                  data?.values[0]?.coordinates,
                  [],
                  data?.values[0]?.confidence,
                  "Y",
                  null
                )
              );
            }
            // [2025-03-11] 체크박스인 경우
            else if (
              data?.values?.length > 0 &&
              (value?.ruleName === "SearchByCheckbox" ||
                value?.selectRuleType === "SearchByCheckbox")
            ) {
              data.values = data?.values?.filter((v) => v?.checked === 1);
              let label = "";
              data?.values?.forEach((v, vIdx) => {
                label += v?.label;
                // if(vIdx < data?.values?.length-1) label += '|';
                if (vIdx < data?.values?.length - 1) label += "";
              });

              resultArr.push(
                resultFormat(
                  keyObj,
                  extrtId,
                  extc_itm_no,
                  1,
                  null,
                  value?.name,
                  data?.keyLabels,
                  label,
                  data?.values[0]?.coordinates,
                  [],
                  data?.values[0]?.confidence,
                  "Y",
                  null
                )
              );
            } else if (category == "납입확인서" && value?.name == "계") {
              keyObj["표추출항목"]?.forEach((k) => {
                let chartValue = data?.values?.filter((v) => {
                  let tmpLabel = "";
                  v?.relativeLabelsInfo?.forEach((rl) => {
                    tmpLabel += rl?.label;
                  });
                  if (k === tmpLabel) {
                    return true;
                  }
                });

                if (chartValue?.length > 0) {
                  // 표추출항목의 values 가 여러 개인 경우
                  // 숫자인 경우 더해서 보여지도록 설정
                  chartValue?.forEach((v) => {
                    v?.relativeLabelsInfo?.forEach((rl, rlIdx) => {
                      resultArr.push(
                        resultFormat(
                          keyObj,
                          extrtId,
                          extc_itm_no,
                          keyObj["표타이틀"]?.indexOf(value?.name) + 1,
                          null,
                          k,
                          rl?.label,
                          v?.label,
                          rl?.coordinates,
                          v?.coordinates,
                          v?.confidence,
                          "Y",
                          value?.name
                        )
                      );

                      extrtId++;
                      extc_itm_no++;
                    });
                  });
                } else {
                  resultArr.push(
                    resultFormat(
                      keyObj,
                      extrtId,
                      extc_itm_no,
                      keyObj["표타이틀"]?.indexOf(value?.name) + 1,
                      null,
                      k,
                      k,
                      null,
                      [],
                      [],
                      1.0,
                      "N",
                      value?.name
                    )
                  );

                  extrtId++;
                  extc_itm_no++;
                }
              });


              // 아래 케이스 생기는 경우 작성
            } else {

              if (data?.values?.length > 0) {
                let label = "";
                if (data?.values?.length > 1)
                  data?.values?.forEach((v) => (label += v?.label));
                else label = data?.values[0]?.label;
                resultArr.push(
                  resultFormat(
                    keyObj,
                    extrtId,
                    extc_itm_no,
                    1,
                    null,
                    value?.name,
                    data?.keyLabels?.join(""),
                    label,
                    data?.values[0]?.coordinates,
                    [],
                    data?.values[0]?.confidence,
                    "Y",
                    null
                  )
                );
              } else {
                resultArr.push(
                  resultFormat(
                    keyObj,
                    extrtId,
                    extc_itm_no,
                    1,
                    null,
                    key,
                    null,
                    null,
                    [],
                    [],
                    1.0,
                    "N",
                    null
                  )
                );
                // resultArr.push(resultFormat(keyObj, extrtId, extc_itm_no, extrtSno, null, value?.name, data?.keyLabels?.join(''), label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, label === null ? "N" : "Y", null));
              }

              // resultArr.push(resultFormat(keyObj, extrtId, extc_itm_no, 0, null, key, null, null, [], [], 1.0, "N", null));
              // resultArr.push(resultFormat(keyObj, extrtId, extc_itm_no, extrtSno, null, value?.name, data?.keyLabels?.join(''), label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, label === null ? "N" : "Y", null));
            }
          });
        });
      }

      if (keyObj["표대상항목"]?.indexOf(key) < 0) {
        extrtId++;
        extc_itm_no++;
      }
    });

    // 공통 포멧 변경
    resultArr.forEach((obj) => {
      // 날짜 포멧 변경
      if (
        typeof keyObj["날짜데이터"] !== "undefined" &&
        keyObj["날짜데이터"]?.length > 0 &&
        keyObj["날짜데이터"]?.indexOf(obj?.img_extc_itnm) >= 0
      ) {
        obj.extrtCntnt = this.setDateFormat(obj?.extrtCntnt);
      }
    });
  }

  // [2026.01.18 영역추출 반영 코드 추가] --- START
  //영역추출 반영 코드 
  // 빈 배열 값을 제거
  const areaResult = areaSearchResult.map(item => ({
    ...item,
    data: item.data.map(dataItem => {
      return Object.fromEntries(
        Object.entries(dataItem).filter(([key, value]) => Array.isArray(value) && value.length > 0)
      );
    })
  }));

  //영역추출 True 인 값만 저장
  let areaChecked = [];
  areaResult?.forEach((area)=>{
    area?.data?.forEach((data)=>{
      Object.entries(data).forEach(([key, value]) => {
        value?.forEach((item) => {
          const arr = new Object();
          arr.name = item.name;
          arr.type = item.sl_type;
          arr.areaFlag = item.value.result;
          arr.areaCoord = item.value.coord;
          arr.dt_tcds = item.sl_type === "useSTA" ? item.dt_tcds : [];
          areaChecked.push(arr);
        });
      });
    })
  })

  //True 인 값(개인정보_동의함)과 항목리스트(개인정보)를 비교하여 value 에 저장 
  areaChecked.forEach((area) => {
    // '_' 기준으로 앞뒤를 분리
    const [itemName, itemValue] = area.name.split('_');
    
    // resultArr에서 해당 itemName이 일치하는 항목을 찾고, extc_rst_cont01에 itemValue를 추가
    resultArr.forEach((result) => {
      
      if (result.img_extc_itnm === itemName) {
        
        if(area.areaFlag === 'True') {
          // [2025-06-09] 서명부 존재시 문구 추가
          if(itemName.includes("서명")) {
            result.extc_rst_cont01 = "Y";
          } else if(area.type === "useSTA") {

            const text = area.dt_tcds?.map(v => v?.mergetext);
            result.extc_rst_cont01 = itemName.includes("주소") ? text.join(" ") : text.join("");

          } else {
            result.extc_rst_cont01 = `${result.extc_rst_cont01 ?? ''} ${itemValue}`.trim();
            // result.extc_rst_cont01 = result.extc_rst_cont01 ? result.extc_rst_cont01 : itemValue;
            // result.extc_rst_cont01 = itemValue;
          }
          result.extrtYn = "Y";
        }
        
        const title = Object.keys(keyObj)[0];
        // [2026.02.11] 좌표값 추가
        if(title.includes("청구서")) {
          
          if((result.img_extc_itnm.includes("피보험자 인적사항-의료수급권자 유무") ||
            result.img_extc_itnm.includes("수익자 인적사항-실제소유자여부") ||
            result.img_extc_itnm.includes("보험금 수령정보-사고연금 신청값") ||
            result.img_extc_itnm.includes("사고관련사항-실손가입여부") ||
            result.img_extc_itnm.includes("안내신청-신청결과 문자안내 유무") ||
            result.img_extc_itnm.includes("안내신청-지급병명 문자안내 유무")) && area.areaFlag === 'True') {
            
            result.extc_rst_img_crdn_vl = area.areaCoord;
          } else {
            result.extc_rst_img_crdn_vl = area.areaCoord;
          }

        } else if(title.includes("동의서")) {

          if(result.img_extc_itnm.includes("체크값")  && area.areaFlag === 'True') {
            result.extc_rst_img_crdn_vl = area.areaCoord;
          } else {
            result.extc_rst_img_crdn_vl = area.areaCoord;
          }
        }

        // result.extc_rst_img_crdn_vl = result.extc_rst_img_crdn_vl.length > 0 ? result.extc_rst_img_crdn_vl : area.areaCoord;
      }
    });
  });
  // [2026.01.18 영역추출 반영 코드 추가] --- END

  // 특정 조건 객체 필터링
  resultArr = filterData(resultArr);

  return resultArr;
};

/**
 * 날짜 포멧 셋팅
 * @param {*} cntnt
 * @returns YYYYMMDD
 */
exports.setDateFormat = function setDateFormat(cntnt) {
  let nowYear = String(new Date().getFullYear());

  if (cntnt === null || cntnt === undefined) return null;

  // 1. 숫자 ./-년월일 외 제거
  cntnt = cntnt.replace(/[^0-9년월일\\.\\/\\~\\-]/g, "");

  if (cntnt === "") return "";

  // 2. .년월일-/ 기준으로 split
  let dateArr = cntnt.split(/년|월|일|\.|\/|\-|\~/);

  let year,
    month,
    day,
    resultDate,
    year2,
    month2,
    day2 = "";
  // 3. 경우에 따라 로직 구현
  // case 1. 추출 된 데이터가 YYYYMMDD 인 경우
  if (cntnt?.length == 10) {
    //기본 형식 ex. 2024-01-12 OR 10자리 이상은 숫자만 그대로 추출
    return dateArr?.join("");
  } else if (cntnt?.length === 9) {
    if (dateArr.length === 1 || dateArr.length === 2) {
      //ex.20240105n , 20241-111, 202412-11...
      resultDate = dateArr?.join("");
    } else if (dateArr.length == 3) {
      if (dateArr[0].length === 4) {
        //ex.2024-1-12, 2024-12-2
        year = dateArr[0];
        if (dateArr[1] < 13 && dateArr[1] >= 1) {
          month = setMmddFormat(dateArr[1]);
          day = setMmddFormat(dateArr[2]);
        } else {
          //ex. 2024-111-, 2024--111
          month = dateArr[1];
          day = dateArr[2];
        }
        resultDate = year + month + day;
      } else {
        resultDate = dateArr?.join("");
      }
    }
    return resultDate;
  } else if (cntnt?.length === 8) {
    if (dateArr.length === 1) {
      //기본 8자리 (ex.20240105)
      return dateArr?.join("");
    } else if (dateArr.length == 2) {
      //ex. 2024-303, 2024-105(1월인지10월인지 구분 안돼서 그대로)
      year = dateArr[0];
      if (year.length === 4) {
        if (dateArr[1].charAt(0) != 1) {
          //2024-303
          month = setMmddFormat(dateArr[1].substr(0, 1));
          day = dateArr[1].substr(1);
        } else {
          //2024-105
          month = dateArr[1];
        }
      } else if (year.length > 4) {
        //ex. 20241-05 , 202412-5
        month = setMmddFormat(year.substr(4, 2));
        year = year.substr(0, 4);
        day = setMmddFormat(dateArr[1]);
      } else year = dateArr?.join("");
      return year + month + day;
    } else if (dateArr.length === 3) {
      //ex. 2024-1-5, 24-11-05
      if (dateArr[0].length === 4) {
        year = dateArr[0];
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      } else if (dateArr[0].length === 2) {
        //ex. 20241-15
        year = setYearFormat(dateArr[0]);
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      } else if (dateArr[0].length === 5) {
        //ex. 20241-5-, 20241-0-
        year = dateArr[0].substr(0, 4);
        month = dateArr[0].substr(4, 1);
        if (dateArr[1] > 2) {
          month = setMmddFormat(month);
        } else month = month;
        day = dateArr[1];
      } else {
        year = dateArr[0];
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      }
      return year + month + day;
    } else {
      return dateArr?.join("");
    }
  } else if (cntnt?.length === 7) {
    if (dateArr.length === 1) {
      //ex. 2024105, 2024305, 2024015
      year = dateArr[0].substr(0, 4);
      let md = dateArr[0].substr(4);
      if (md.substr(0, 1) == 0) {
        //ex.2024015
        month = md.substr(0, 2);
        day = setMmddFormat(md.substr(2));
      } else if (md.substr(0, 1) == 1 && md.substr(1, 1) < 3) {
        //ex. 2024105 (1월인지 10월인지 모르기 때문에 그대로 추출)
        month = md;
      } else if (md.substr(0, 1) > 1) {
        //ex.2024305
        month = setMmddFormat(md.substr(0, 1));
        day = md.substr(1);
      }
      return year + month + day;
    } else if (dateArr.length == 2) {
      // 오인식 (ex. 20241-05, 20241-5, 202411-05,202411-5...)
      if (dateArr[0].length == 2) {
        //ex. 24-0103
        year = setYearFormat(dateArr[0]);
        if (dateArr[1].length == 4) {
          month = dateArr[1].substr(0, 2);
          day = dateArr[1].substr(2, 2);
        } else {
          resultDate = dateArr?.join("");
        }
        resultDate = year + month + day;
      } else if (dateArr[0]?.length === 4) {
        //ex.2024-15, 2401-15 구분이 명확하지 못함으로 그대로 추출
        year = dateArr[0].substr(0, 2);
        month = dateArr[0].substr(2, 2);
        day = dateArr[1];
        if (month >= 1 && month <= 12) {
          //가운데 두자리가 1~12일 경우만 YYMMDD
          year = setYearFormat(year);
          month = setMmddFormat(month);
          day = setMmddFormat(day);
        } else {
          if (day > 12) {
            //가운데 두자리가 12 초과 일 경우는 그대로
            year = dateArr[0];
            month = setMmddFormat(day.substr(0, 1));
            day = setMmddFormat(day.substr(1));
          }
        }
        resultDate = year + month + day;
      } else if (dateArr[0].length == 5) {
        //ex. 20241-2, 20241-5, 20243-6...
        year = dateArr[0].substr(0, 4);
        month = setMmddFormat(dateArr[0].substr(4));
        day = setMmddFormat(dateArr[1].substr(0, 2));
        resultDate = year + month + day;
      } else resultDate = dateArr?.join("");
      return resultDate;
    }
  } else if (cntnt?.length === 6) {
    if (dateArr.length === 1) {
      //ex. 240103,202411 -가운데 두자리가 1~12일 경우만 YYMMDD, 이외는 그대로 추출
      year = cntnt.substr(0, 2);
      month = cntnt.substr(2, 2);
      day = cntnt.substr(4, 2);
      if (month >= 1 && month <= 12) {
        year = setYearFormat(year);
        month = setMmddFormat(month);
        day = setMmddFormat(day);
      }
      return year + month + day;
    } else if (dateArr.length === 2) {
      if (dateArr[0].length === 2) {
        //ex.24-115, 24-015, 24-615...
        year = setYearFormat(dateArr[0]);
        if (dateArr[1].charAt(0) == 0) {
          //ex. 24-015
          month = dateArr[1].substr(0, 2);
          day = setMmddFormat(dateArr[1].substr(2));
        } else if (dateArr[1].charAt(0) == 1) {
          month = dateArr[1];
        } else {
          month = setMmddFormat(dateArr[1].substr(0, 1));
          day = dateArr[1].substr(1);
        }
      } else if (dateArr[0].length === 4) {
        //ex. 2024-3,  2401-5
        year = dateArr[0].substr(0, 2);
        month = dateArr[0].substr(2, 2);
        day = setMmddFormat(dateArr[1]);
        if (month >= 1 && month <= 12) {
          //2401-5
          year = setYearFormat(year);
          month = setMmddFormat(month);
        } else {
          //2024-3
          year = dateArr[0];
          month = setMmddFormat(dateArr[1]);
          day = "";
        }
      } else {
        //ex. 241-15, 20241-
        year = dateArr?.join("");
        month = "";
        day = "";
      }
      resultDate = year + month + day;
      return resultDate;
    } else if (dateArr.length === 3) {
      if (dateArr[0].length == 2) {
        //ex. 24-1-1, 24-51-, 24--51
        year = setYearFormat(dateArr[0]);
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      } else {
        //ex. 2024--
        year = dateArr?.join("");
        month = "";
        day = "";
      }
      resultDate = year + month + day;
      return resultDate;
    }
  }
  // else if(cntnt?.lenght==12){
  //   let firstDate, secondDate;
  //   if(dateArr.length ==1){
  //     firstDate = dateArr[0].substr(0,6);
  //     secondDate =dateArr[0].substr(6,6);
  //   }
  // }
  else if (cntnt?.length === 13 && dateArr.length == 2) {
    if (dateArr[0].length == 6) {
      year = cntnt.substr(0, 2);
      month = cntnt.substr(2, 2);
      day = cntnt.substr(4, 2);
      if (month >= 1 && month <= 12) {
        year = setYearFormat(year);
        month = setMmddFormat(month);
        day = setMmddFormat(day);
      }
      dateArr[0] = year + month + day;
    }
    if (dateArr[1].length == 6) {
      year = cntnt.substr(0, 2);
      month = cntnt.substr(2, 2);
      day = cntnt.substr(4, 2);
      if (month >= 1 && month <= 12) {
        year = setYearFormat(year);
        month = setMmddFormat(month);
        day = setMmddFormat(day);
      }
      dateArr[1] = year + month + day;
    }
    return dateArr.join("");
  } else if (cntnt?.length == 16) {
    if (dateArr.length == 1) {
      return dateArr.join("");
    } else if (dateArr.length == 5 && dateArr[2].length == 4) {
      //22.02.11~22.02.24
      resultDate =
        setYearFormat(dateArr[0]) +
        setMmddFormat(dateArr[1]) +
        setMmddFormat(dateArr[2].substr(0, 2));
      resultDate =
        resultDate +
        setYearFormat(dateArr[2].substr(2, 4)) +
        setMmddFormat(dateArr[3]) +
        setMmddFormat(dateArr[4]);
      return resultDate;
    } else return dateArr.join("").substr(0, 16);
  } else if (cntnt?.length === 17) {
    if (dateArr.length == 2) {
      return dateArr.join("").substr(0, 16);
    } else if (dateArr.length == 6) {
      //22.02.12-22.02.24
      resultDate =
        setYearFormat(dateArr[0]) +
        setMmddFormat(dateArr[1]) +
        setMmddFormat(dateArr[2]);
      resultDate =
        resultDate +
        setYearFormat(dateArr[3]) +
        setMmddFormat(dateArr[4]) +
        setMmddFormat(dateArr[5]);
      return resultDate;
    } else return dateArr.join("");
  } else if (cntnt !== undefined && cntnt?.length === 20) {
  }
  // else if(cntnt?.length==20){
  //   // if(dateArr.length==6){
  //   //   resultDate = setYearFormat(dateArr[0])+ setMmddFormat(dateArr[1])+setMmddFormat(dateArr[2])
  //   //   resultDate= resultDate+ setYearFormat(dateArr[3])+ setMmddFormat(dateArr[4])+setMmddFormat(dateArr[5]);
  //   // }else return dateArr.join('');
  // }
  else {
    //2021-08-10~2021-08-10, 그외..
    return dateArr.join("");
  }
};

/**
 * 2024.09.23 루나
 * @param {*} year
 * @returns
 */
function setYearFormat(year) {
  let cntntYear = year.substr(0, 2); // 앞의 두 자리를 연도로 추출
  let monthDay = year.substr(2); // 나머지 부분은 월과 일로 처리

  // 현재 연도의 마지막 두 자리를 추출
  let currentYear = String(new Date().getFullYear()).substr(2, 2);

  let fullYear = cntntYear <= currentYear ? "20" + cntntYear : "19" + cntntYear;

  return fullYear;
}

/**
 * 2024.09.23 루나
 * @param {*} date
 * @returns
 */
function setMmddFormat(date) {
  return date?.length === 1 ? "0" + date : date;
}

/**
 * @name resultFormat
 * @description 일정한 result 포맷 형식으로 정리하여 반환한다.
 * @returns 
 */
function resultFormat(
  keyObj,
  extrtId,
  extc_itm_no,
  extrtSno,
  uppExtrtItmNm,
  img_extc_itnm,
  extrtRawItmNm,
  extrtCntnt,
  itmValCoordVal,
  itmNmCoordVal,
  selfRlbtyVal,
  extrtYn,
  extc_rst_cont08= null,
  extc_itm_tpvl = null,
  extc_rst_cont09 = null,
  extc_rst_cont10 = null,
  index = null,
  relativeIndex = null
) {
  if (Object.keys(keyObj).length < 1)
    keyObj = { 추출항목: [], 표타이틀: [], 표추출항목: [], 표레이블: [] };

  if (typeof selfRlbtyVal !== "number") selfRlbtyVal = parseFloat(selfRlbtyVal);
  if (isNaN(selfRlbtyVal)) selfRlbtyVal = 0;

  if (typeof extrtCntnt === "undefined" || extrtCntnt === undefined) extrtCntnt = "";
  if (typeof extc_rst_cont08 === "undefined" || extc_rst_cont08 === undefined) extc_rst_cont08 = null;
  if (typeof extc_itm_tpvl === "undefined" || extc_itm_tpvl === undefined) extc_itm_tpvl = null;
  if (typeof extc_rst_cont09 === "undefined" || extc_rst_cont09 === undefined) extc_rst_cont09 = null;
  if (typeof extc_rst_cont10 === "undefined" || extc_rst_cont10 === undefined) extc_rst_cont10 = null;

  let result = {
      lvl_no: extc_rst_cont09 != null ? 2 : 1          // (int) 레벨번호
    , extc_itm_no: extc_itm_no || 1                    // (int) 추출항목번호
    , extc_rst_seq: extrtSno !== 0 ? extrtSno : 1      // (int) 추출결과일련번호
    , hgrk_extc_itm_no: ["1인실", "2·3인실", "4인실이상"].includes(img_extc_itnm) && extc_rst_cont09 == "입원료" ?
                          IPF_HGRK_EXTC_ITM_NO :
                        ["행위료", "약품비"].includes(img_extc_itnm) && extc_rst_cont09 == "투약및조제료" ?
                          DNF_HGRK_EXTC_ITM_NO : 
                        ["행위료", "약품비"].includes(img_extc_itnm) && extc_rst_cont09 == "주사료" ?
                          INF_HGRK_EXTC_ITM_NO : 0              // 상위레벨번호
    , index: index
    , relativeIndex: relativeIndex
    , extc_itm_tpvl: (extc_itm_tpvl == "기본항목" || extc_itm_tpvl == "선택항목") ? extc_itm_tpvl : null   // 상위항목값

    , extc_hgrk_itnm : extc_rst_cont09 || null  // (String) 상위추출항목명 ex) 입원료, 투약및조제료, 주사료
    , img_extc_itnm: img_extc_itnm            // (String) 추출항목명
    , extc_rst_cont01: extrtCntnt || ""    // (String) 추출내용
    , extc_rst_cont08: extc_rst_cont08 || null // 유관관계성항목명
    , extc_rst_cont09: extc_rst_cont09 || null // Depth2
    , extc_rst_cont10: extc_rst_cont10 // table 구분

    , extrtYn: extrtYn || "N"              // (String) 추출여부 - 이미지에서 추출 됐으면 Y, 없으면 N

    , extc_rst_img_crdn_vl : itmValCoordVal || []                // (String) 항목값좌표값
    , self_rlbtr_vl: Math.floor(selfRlbtyVal * 100) / 100 || 1.0 // (float) 본인신뢰도값
  };

  return result;
}

/**
 * @name filterData
 * @description (조건 1) img_extc_itnm이 TARGET_ITEMS 해당
 *              (조건 2) extrtYn 값이 N
 *              (결과  ) 해당된 items 중 extc_rst_seq 값 1을 제외하고 모든 객체 제거
 * @returns 
 */
function filterData(list) {

  const TARGET_ITEMS = new Set([
    '입원료',
    '투약및조제료',
    '주사료',
  ]);

  return list.filter(item => {
    const isTargetItem = TARGET_ITEMS.has(item.img_extc_itnm);
    const isExtrtN = item.extrtYn === 'N';
    const isNotFirstSeq = item.extc_rst_seq !== 1;
    const isDetph2Yn = item.extc_rst_cont09 != null ? true : false;

    // 삭제 조건에 해당하면 false → 제거
    if (isTargetItem && isExtrtN && isNotFirstSeq && !isDetph2Yn) {
      return false;
    }

    // 그 외는 유지
    return true;
  });
}
