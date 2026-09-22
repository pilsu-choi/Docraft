// const {Logger}            = require('common/logger');
const { Logger } = require('/usr/src/app/dist/apps/extn/libs/common/src/logger');

// const pluginUtil  = require("./pluginUtil.js");


const pluginUtilCache = require.resolve("./pluginUtil_진단서5종.js");
delete require.cache[pluginUtilCache];
const pluginUtil = require(pluginUtilCache);

exports.setResultFormat = function setResultFormat(values, keyObj, arrtcd, category) {
  let resultArr = [];
  let extrtId = 1;
  let lvlNo = 1;

  // 진료비영수증의 표데이터 추출레벨번호 처리를 위해 작성
  let chartLvlNo = 0;
  let rlChartYN = false;  // TODO 한 문서에 relativeLabelsInfo, relativeValueKeywordInfo 둘 다 사용하는 경우가 생기면 추가 작업 필요

  // 영역 추출 결과 
  let areaSearchResult = values?.filter((value) => value?.ruleName === 'AreaSearch');

  // values 에서 불필요한 값 제거
  values = values?.filter((value) => value?.ruleName !== 'CollectTabularData' && value?.ruleName !== 'CollectStrikeThroughData' && value?.ruleName !== 'AreaSearch');

  // 스키마에는 정의되어 있으나, 항목리스트.json 에는 정의되지 않은 경우에 대한 처리 (항목리스트.json 에 추가처리여부 정의)
  // 항목리스트 추출항목에 정의 된 항목이 없는 경우
  let afterItmYN = keyObj["추가처리여부"];
  if (afterItmYN === "Y" || keyObj["추출항목"]?.length < 1) {
    values?.filter((value) => keyObj["추출항목"]?.indexOf(value?.name) < 0)
      .forEach((value) => {
        // 추출항목 마지막에 추가
        keyObj["추출항목"].push(value?.name);
      });

    // 표대상항목 중 항목리스트 표추출항목에 정의 된 항목이 없는 경우
    values?.filter((value) => keyObj["표대상항목"]?.indexOf(value?.name) >= 0)
      .forEach((value) => {
        value?.data?.forEach((data) => {
          data?.values
            .filter((v) => { return v?.relativeLabelsInfo?.length > 0 ? true : false; })
            .forEach((v) => {
              if (v?.relativeLabelsInfo?.length > 0) {
                rlChartYN = true;
                //진료비영수증은 항목리스트에 정해진것만 추출하게하기
                if (category == '통원의료비영수증') {
                  v?.relativeLabelsInfo?.forEach((rl) => {
                    // if(keyObj["표추출제외항목"]?.indexOf(rl?.label) < 0 && keyObj["표추출항목"]?.indexOf(rl?.label) < 0)
                    //   keyObj["표추출항목"]?.push(rl?.label);
                  });
                }
              }
            });
        });
      });

    keyObj["추출항목"] = keyObj["추출항목"]?.filter((key) => key !== '');
  }

  // 후처리항목이 있는 경우 표추출항목의 순서 변경되도록 설정
  keyObj["표추출항목"] = keyObj["표추출항목"]?.sort((a, b) => {
    return keyObj["후처리항목"]?.indexOf(a) - keyObj["후처리항목"]?.indexOf(b);
  });

  // resultArr push 로직 시작
  if (typeof values !== 'undefined' && values?.length > 0) {

    keyObj["추출항목"]?.forEach((key, i) => {
      let itmValue = values?.filter((value) => value?.name === key && value?.data?.length > 0);

      if (itmValue?.length < 1) {
        resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, key, null, null, [], [], 1.0, "N", null));
      }
      else {
        itmValue?.forEach((value) => {
          // 여러 번 출력 된 경우 status 가 0 아래 값 제거 후 label 합치기
          if (value?.data?.length > 1) {
            // [2025-04-16] status가 -1인 값(keyword 미추출)만 제거
            // value.data = value?.data?.filter((data) => data?.status >= 0 && !value?.selectRuleType?.includes("Check"));
            value.data = value?.data?.filter((data) => (data?.status !== -1) && !value?.selectRuleType?.includes("Check"));
          }

          // [2025-03-11] value?.data에 값이 없는 경우 처리
          if (value?.data?.length === 0) {
            resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, key, null, null, [], [], 1.0, "N", null));
          }

          value?.data?.forEach((data) => {
            // 표데이터
            if (keyObj["표대상항목"]?.indexOf(value?.name) >= 0) {
              // relativeLabelsInfo 를 사용하는 경우 (ex. 진료비영수증)
              if (rlChartYN) {
                if (keyObj["표대상항목"]?.indexOf(value?.name) === 0) chartLvlNo = lvlNo;
                else lvlNo = chartLvlNo;

                keyObj["표추출항목"]?.forEach((k) => {

                  let chartValue = data?.values?.filter((v) => {
                    let tmpLabel = '';
                    v?.relativeLabelsInfo?.forEach((rl) => {
                      tmpLabel += rl?.label

                    });
                    if (k === tmpLabel) {
                      return true;
                    }
                  });

                  if (chartValue?.length > 0) {
                    // 표추출항목의 values 가 여러 개인 경우
                    // 숫자인 경우 더해서 보여지도록 설정
                    if (chartValue?.length > 1) {
                      if (k !== '입원료') Logger.log('🚨🚨🚨🚨🚨🚨🚨 표추출항목이 여러개인 경우'); // JSON.stringify(chartValue, null, 1)

                      let numLabel = 0;
                      chartValue?.forEach((o) => {
                        let tmpLabel = o?.label?.replace(/[^0-9]/gi, '');
                        tmpLabel = isNaN(tmpLabel) ? 0 : Number(tmpLabel);

                        numLabel += tmpLabel;
                      });
                      if (numLabel > 0) {
                        chartValue[0].label = numLabel;
                        chartValue[0].relativeLabelsInfo[0].label = k;
                      }

                      chartValue = [chartValue[0]];
                    }

                    chartValue?.forEach((v) => {
                      v?.relativeLabelsInfo?.forEach((rl, rlIdx) => {

                        resultArr.push(resultFormat(keyObj, extrtId, lvlNo, (keyObj["표타이틀"]?.indexOf(value?.name) + 1), null, k, rl?.label, v?.label, rl?.coordinates, v?.coordinates, v?.confidence, "Y", value?.name));

                        extrtId++;
                        lvlNo++;
                      });
                    });
                  } else {
                    resultArr.push(resultFormat(keyObj, extrtId, lvlNo, (keyObj["표타이틀"]?.indexOf(value?.name) + 1), null, k, k, null, [], [], 1.0, "N", value?.name));

                    extrtId++;
                    lvlNo++;
                  }
                });
              }
              // relativeValueKeywordInfo 를 사용하는 경우 (ex. 진료비세부내역서)
              else {

                let chartTitle = keyObj["표타이틀"];
                if (chartTitle.length < 1 && keyObj[`표타이틀_` + key]?.length > 0) {
                  chartTitle = keyObj[`표타이틀_` + key];
                }


                data?.values?.forEach((v) => {
                  v?.relativeValueInfo?.forEach((r) => {
                  })
                  let extrtSno = 0;
                  let valueSno = 0;

                  if (afterItmYN === "Y") {
                    chartTitle?.forEach((tv, ti) => {
                      extrtSno++;


                      // 추출 정의 항목과 추출된 key가 같은 경우 정의된 룰대로 push
                      if (tv === v?.relativeValueInfo[valueSno]?.keyLabels?.join('_')) {
                        resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, v?.relativeValueInfo[valueSno]?.keyLabels?.join(''), v?.relativeValueInfo[valueSno]?.keyLabels?.join(''), v?.relativeValueInfo[valueSno]?.label, v?.relativeValueInfo[valueSno]?.coordinates, v?.coordinates, v?.relativeValueInfo[valueSno]?.confidence, "Y", value?.name));
                        valueSno++;
                        // 추출 정의 항목과 추출된 key가 같지 않은 경우
                      } else {
                        // 메인 key로 뽑은 경우
                        if (tv === data?.keyLabels?.join('')) {
                          resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, tv, tv, v?.label, v?.coordinates, v?.coordinates, v?.confidence, "Y", value?.name));
                          // 추출되지 않은 경우 'N'으로 PUSH
                        } else {
                          resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, tv, tv, null, [], [], 1.0, "N", value?.name));
                        }
                      }
                    });
                  } else {
                    // relativeValueKeywordInfo 로 정의 된 룰에 의한 추출 값
                    v?.relativeValueInfo?.forEach((rv) => {
                      extrtSno++;
                      resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, rv?.keyLabels?.join(''), rv?.keyLabels?.join(''), rv?.label, rv?.coordinates, v?.coordinates, rv?.confidence, "Y", value?.name));
                    });
                  }

                  extrtId++;
                  lvlNo++;
                });
              }

            }

            else if (value.name === "병명" || value.name === "수술명") {

              // 0) 병명코드처럼 보이는 mergecell 제외
              // const diagCells = (data.values ?? []).filter(cell => {
              //   const rawLabel = String(cell?.label ?? "");
              //   const cleaned = rawLabel.replace(/[^A-Za-z0-9]/g, "");
              //   const isCodeLike =
              //     cell?.cellType === "mergecell" &&
              //     /^[A-Za-z][0-9]{3,5}[A-Za-z0-9]*$/.test(cleaned);
              //   return !isCodeLike;
              // });
              const diagCells = data.values ?? [];

              // 1) "조각(piece)" 만들기: 가능하면 ocrInfo 단위로 쪼개서 좌표 기반 행판단 정확도 ↑
              const pieces = [];
              for (const cell of diagCells) {
                if (Array.isArray(cell?.ocrInfo) && cell.ocrInfo.length > 0) {
                  for (const o of cell.ocrInfo) {
                    const text = String(o?.label ?? "").replace(/\s+/g, " ").trim();
                    if (!text) continue;

                    const yTop = o?.coordinates?.[1] ?? cell?.coordinates?.[1] ?? 0;
                    const yBot = o?.coordinates?.[5] ?? cell?.coordinates?.[5] ?? yTop;
                    const yMid = (yTop + yBot) / 2;
                    const xLeft = o?.coordinates?.[0] ?? cell?.coordinates?.[0] ?? 0;

                    pieces.push({ text, yMid, yBottom: yBot, xLeft });
                  }
                } else {
                  const text = String(cell?.label ?? "").replace(/\s+/g, " ").trim();
                  if (!text) continue;

                  const yTop = cell?.coordinates?.[1] ?? 0;
                  const yBot = cell?.coordinates?.[5] ?? yTop;
                  const yMid = (yTop + yBot) / 2;
                  const xLeft = cell?.coordinates?.[0] ?? 0;

                  pieces.push({ text, yMid, yBottom: yBot, xLeft });
                }
              }

              // 조각이 없으면 빈값 처리
              if (pieces.length === 0) {
                resultArr.push(resultFormat(
                  keyObj, extrtId, lvlNo, 0, null,
                  value?.name, data?.keyLabels?.join(""),
                  "", [], [], 1.0, "N", null
                ));
              } else {
                // 2) y 기준 정렬 후 행 그룹핑
                pieces.sort((a, b) => (a.yMid - b.yMid) || (a.xLeft - b.xLeft));

                const rowGap = 8; // 필요하면 튜닝 (10~15로 올리기도 함)
                const rows = [];
                for (const p of pieces) {
                  const lastRow = rows[rows.length - 1];
                  if (!lastRow) {
                    rows.push([p]);
                    continue;
                  }
                  const baseY = lastRow[0].yMid;
                  if (Math.abs(p.yMid - baseY) <= rowGap) lastRow.push(p);
                  else rows.push([p]);
                }

                // 3) 행 내부는 x 기준 정렬 후 공백 join
                let rowTexts = rows.map(row =>
                  row.sort((a, b) => a.xLeft - b.xLeft).map(r => r.text).join(" ")
                );

                const lastRow = rows[rows.length - 1];

                const lastRowBottomY = lastRow
                  ? Math.max(...lastRow.map(p => p.yBottom ?? p.yMid ?? 0))
                  : null;

                const lastRowFirstX = lastRow
                  ? Math.min(...lastRow.map(p => p.xLeft ?? 0))
                  : null;

                // const near = filterArrtcdNearLastRowBottomY(arrtcd, lastRowBottomY, lastRowFirstX, 5, 10, 500);
                // const merged = mergeNearTexts(near); // "추가 텍스트" 후보

                // ✅ merged를 rowTexts에 반영 (새 행인지/연장인지 판단)
                rowTexts = expandDiagnosisByNearLines({
                  rowTexts,
                  arrtcd,
                  startBottomY: lastRowBottomY,
                  startFirstX: lastRowFirstX,
                  yTol: 15,
                  xLeftTol: 10,
                  xRightTol: 500,
                  maxSteps: 10
                });

                Logger.log("TR 병명or수술명 추출 값 = " + rowTexts)
                const dateCutExp = /\d{2,4}년\s*\d{1,2}월\s*\d{1,2}일/;

                const cleanedRowTexts = rowTexts.map(text => {
                  //진단연월일~~~ 로 이상한 값이 추출될때 지우기
                  const diagIdx = text.indexOf("진단연월일");
                  if (diagIdx !== -1) {
                    return text.slice(0, diagIdx).trim();
                  }
                  //날짜 패턴 지우기
                  const match = text.match(dateCutExp);
                  if (match) {
                    return text.slice(0, match.index).trim();
                  }

                  return text;
                }).filter(Boolean); // 빈 문자열 제거

                // 4) 행이 1개면 공백문장, 2개 이상이면 $$$로 분리
                const mergedText = cleanedRowTexts.length <= 1
                  ? cleanedRowTexts[0]
                  : cleanedRowTexts.join("$$$");

                // 좌표/신뢰도는 본문셀 우선
                const mainCell =
                  (data.values ?? []).find(v => v?.cellType === "cell") ??
                  (data.values ?? [])[0];

                resultArr.push(resultFormat(
                  keyObj, extrtId, lvlNo, 0, null,
                  value?.name, data?.keyLabels?.join(""),
                  mergedText,
                  mainCell?.coordinates, [],
                  mainCell?.confidence,
                  "Y", null
                ));
              }
            }
            else if (value.name === "진료과") {
              value?.data?.forEach(data => {
                data?.values?.forEach(values => {

                  let deptArr = [];

                  // 1) ocrInfo가 있으면 그대로 사용
                  if (Array.isArray(values?.ocrInfo) && values.ocrInfo.length > 0) {
                    deptArr = values.ocrInfo
                      .map(o => String(o?.label ?? "").trim())
                      .filter(Boolean);
                  } else {
                    // 2) 백업: label에서 '과' 단위로 분리
                    const raw = String(values?.label ?? "").trim();
                    const matches = raw.match(/.+?과/g);
                    if (matches) deptArr = matches.map(v => v.trim());
                  }

                  // 3) $$$ 로 병합
                  const mergedText = deptArr.join("$$$");

                  // 4) 좌표 / confidence 기준 셀
                  const mainCell =
                    (data?.values ?? []).find(v => v?.cellType === "cell") ??
                    values;

                  // 5) 결과 push
                  resultArr.push(resultFormat(
                    keyObj,
                    extrtId,
                    lvlNo,
                    0,
                    null,
                    value?.name,                 // "진료과"
                    data?.keyLabels?.join(""),
                    mergedText,
                    mainCell?.coordinates ?? [],
                    [],
                    mainCell?.confidence ?? 1.0,
                    mergedText ? "Y" : "N",
                    null
                  ));
                });
              });
            }
            else if (value.name == "환자 등록번호") {
              let firstcellX = data?.values[0]?.coordinates[0];
              let label = ''
              data?.values?.forEach(v => {
                if (v.coordinates[0] - firstcellX > 300) {
                  v.label = ""
                }
                label += v?.label
              })
              resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, value?.name, data?.keyLabels?.join(''), label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "Y", null));
            }
            // 추출 된 결과가 없는 경우 
            else if (data?.values?.length < 1) {
              // resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, value?.name, data?.keyLabels?.join(''), null, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "N", null));
              // [2025-04-15] status -1 은 'N' 처리
              if (data?.status === -1) {
                resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, value?.name, data?.keyLabels?.join(''), null, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "N", null));
              }
              else if (data?.status === -3) {
            
              }
              else {
                // [2025-04-13] value?.data에 값이 없는 경우 'Y' 처리 (keyword만 추출, 값은 없는 경우)
                resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, value?.name, data?.keyLabels?.join(''), null, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "Y", null));
              }
            }
            // 한 가지 항목만 추출 된 경우
            else if (data?.values?.length > 0 && data?.values[0]?.relativeLabelsInfo?.length < 1 && data?.values[0]?.relativeValueInfo?.length < 1) {
              let label = '';
              
              //입원확인서,수술확인서 경우 (수술일자, 수술명 여러개 추출)
              if ((category === "Y000701300" || category === "Y00071250") && (value.name == "수술일자" || value.name == "수술명")) {
                if (data?.values?.length > 1) {
                  if (value.name == "수술일자" && !(data?.values[0]?.label.includes("입원수술"))) {
                    label = data.values.map(v =>
                      Array.isArray(v?.label) ? v.label.join("$$$") : v?.label
                    ).join("$$$")
                  }
                  else label = data.values.map(v =>
                    Array.isArray(v?.label) ? v.label.join("") : v?.label
                  ).join("")
                }
                else label = data?.values[0]?.label;
              }
              else {
                
                if (data?.values?.length > 1) {
                  data?.values?.forEach((v) => label += v?.label);
                }
                else {
                  label = data?.values[0]?.label;
                }
              }
              resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, value?.name, data?.keyLabels?.join(''), label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "Y", null));
            }
            // [2025-03-11] 체크박스인 경우
            else if (data?.values?.length > 0 && (value?.ruleName === 'SearchByCheckbox' || value?.selectRuleType === 'SearchByCheckbox')) {
              data.values = data?.values?.filter((v) => v?.checked === 1);
              let label = '';
              data?.values?.forEach((v, vIdx) => {
                label += v?.label;
                // if(vIdx < data?.values?.length-1) label += '|';
                if (vIdx < data?.values?.length - 1) label += '';
              });
              resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, value?.name, data?.keyLabels, label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "Y", null));
            }
            else if (category == "납입확인서" && value?.name == "계") {
              keyObj["표추출항목"]?.forEach((k) => {
                let chartValue = data?.values?.filter((v) => {
                  let tmpLabel = '';
                  v?.relativeLabelsInfo?.forEach((rl) => {
                    tmpLabel += rl?.label

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
                    
                      resultArr.push(resultFormat(keyObj, extrtId, lvlNo, (keyObj["표타이틀"]?.indexOf(value?.name) + 1), null, k, rl?.label, v?.label, rl?.coordinates, v?.coordinates, v?.confidence, "Y", value?.name));

                      extrtId++;
                      lvlNo++;
                    });
                  });
                } else {
                  resultArr.push(resultFormat(keyObj, extrtId, lvlNo, (keyObj["표타이틀"]?.indexOf(value?.name) + 1), null, k, k, null, [], [], 1.0, "N", value?.name));

                  extrtId++;
                  lvlNo++;
                }


              });


              // 아래 케이스 생기는 경우 작성
            }
            else {
              Logger.log('🚨🚨🚨🚨🚨🚨🚨 케이스 테스트 필요 \t'+value?.name);
              if (data?.values?.length > 0) {
                let label = '';
                if (data?.values?.length > 1)
                  data?.values?.forEach((v) => label += v?.label);
                else
                  label = data?.values[0]?.label;
                resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, value?.name, data?.keyLabels?.join(''), label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "Y", null));
              } else {
                resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, key, null, null, [], [], 1.0, "N", null));
                // resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, value?.name, data?.keyLabels?.join(''), label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, label === null ? "N" : "Y", null));
              }
              // resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, key, null, null, [], [], 1.0, "N", null));
              // resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, value?.name, data?.keyLabels?.join(''), label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, label === null ? "N" : "Y", null));
            }


          });
        });
      }

      if (keyObj["표대상항목"]?.indexOf(key) < 0) {
        extrtId++;
        lvlNo++;
      }
    });

    // 공통 포멧 변경
    resultArr.forEach((obj) => {
      // 날짜 포멧 변경
      if (!((category == "Y000701300" || category == "Y00071250") && obj.img_extc_itnm == "수술일자")) {
        if (typeof keyObj["날짜데이터"] !== 'undefined' && keyObj["날짜데이터"]?.length > 0 && keyObj["날짜데이터"]?.indexOf(obj?.img_extc_itnm) >= 0) {
          obj.extc_rst_cont01 = this.setDateFormat(obj?.extc_rst_cont01);
        }
      }
    });
  }

  return resultArr;
}
/**
 * 날짜 포멧 셋팅 _old
 * @param {*} cntnt 
 * @returns YYYYMMDD
 */
exports.setDateFormat = function setDateFormat(cntnt) {
  let nowYear = String(new Date().getFullYear());
  // 1. 숫자 ./-년월일 외 제거
  cntnt = cntnt?.replace(/[^0-9년월일\\.\\/\\~\\-]/g, '');

  if (cntnt === '') return '';

  // 2. .년월일-/ 기준으로 split
  let dateArr = cntnt.split(/년|월|일|\.|\/|\-|\~/);
  // Logger.log("🍩🍩"+ cntnt+ "=> "+ dateArr+ "====>"+ dateArr.length+ "==>"+ cntnt.length)

  let year, month, day, resultDate, year2, month2, day2 = '';
  // 3. 경우에 따라 로직 구현
  // case 1. 추출 된 데이터가 YYYYMMDD 인 경우
  if (cntnt?.length == 3) {
    if (dateArr.length == 2) {
        month = setMmddFormat(dateArr[0])
        day = setMmddFormat(dateArr[1])
        resultDate = month + day
      return resultDate
    }
    else return dateArr?.join('')
  }
  if (cntnt?.length == 4 ) {
    if (dateArr.length == 2) {//['2','12']
        month = setMmddFormat(dateArr[0])
        day = setMmddFormat(dateArr[1])
        resultDate = month + day
      return resultDate
    }
    if (dateArr.length == 3 && dateArr[2] == '') { //['2','12','']
      if (cntnt.includes("월") && cntnt.includes("일")) {
        month = setMmddFormat(dateArr[0])
        day = setMmddFormat(dateArr[1])
        resultDate = month + day
      }
      return resultDate
    }
    else return dateArr?.join('')
  }
  if ( cntnt?.length == 5) {
    if (dateArr.length == 3 && dateArr[2] == '') { //['2','12','']
      if (cntnt.includes("월") && cntnt.includes("일")) {
        month = setMmddFormat(dateArr[0])
        day = setMmddFormat(dateArr[1])
        resultDate = month + day
      }
      return resultDate
    }
    else return dateArr?.join('')
  }
  if (cntnt?.length == 10) { //기본 형식 ex. 2024-01-12 OR 10자리 이상은 숫자만 그대로 추출
    if (dateArr.length == 4) {
      if (dateArr[0].length === 4) { //ex.2024-1-12, 2024-12-2
        year = dateArr[0];
        if (dateArr[1] < 13 && dateArr[1] >= 1) {
          month = setMmddFormat(dateArr[1]);
          day = setMmddFormat(dateArr[2])
        }
        else { //ex. 2024-111-, 2024--111
          month = dateArr[1];
          day = dateArr[2];
        }
        resultDate = year + month + day;
      } else {
        resultDate = dateArr?.join('');
      }
      return resultDate
    }
    else return dateArr?.join('')
  }

  else if (cntnt?.length === 9) {
    // Logger.log("1️⃣. 9자리 경우 1️⃣")
    if (dateArr.length === 1 || dateArr.length === 2) { //ex.20240105n , 20241-111, 202412-11...
      resultDate = dateArr?.join('');
    }
    else if (dateArr.length == 3 || dateArr.length == 4) {
      if (dateArr[0].length === 4) { //ex.2024-1-12, 2024-12-2
        year = dateArr[0];
        if (dateArr[1] < 13 && dateArr[1] >= 1) {
          month = setMmddFormat(dateArr[1]);
          day = setMmddFormat(dateArr[2])
        }
        else { //ex. 2024-111-, 2024--111
          month = dateArr[1];
          day = dateArr[2];
        }
        resultDate = year + month + day;
      }
      else if (dateArr[0].length == 2 && dateArr[1].length == 2 && dateArr[2].length == 2 && dateArr[3].length == 0) {
        year = setYearFormat(dateArr[0]);
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
        resultDate = year + month + day;
      } else if (dateArr[0].length != 4) {
        resultDate = dateArr?.join('');
      }
    }
    return resultDate;
  }
  else if ((cntnt?.length === 8)) {
    // Logger.log("1️⃣. 8자리 경우 1️⃣")
    if (dateArr.length === 1) { //기본 8자리 (ex.20240105)
      return dateArr?.join('');
    }
    else if (dateArr.length == 2) { //ex. 2024-303, 2024-105(1월인지10월인지 구분 안돼서 그대로)
      year = dateArr[0];
      if (year.length === 4) {
        if (dateArr[1].charAt(0) != 1) { //2024-303
          month = setMmddFormat(dateArr[1].substr(0, 1));
          day = dateArr[1].substr(1,)
        }
        else { //2024-105
          month = dateArr[1];
        }
      }
      else if (year.length > 4) { //ex. 20241-05 , 202412-5
        month = setMmddFormat(year.substr(4, 2));
        year = year.substr(0, 4);
        day = setMmddFormat(dateArr[1]);
      }
      else year = dateArr?.join('')
      return year + month + day;
    }
    else if (dateArr.length === 3) { //ex. 2024-1-5, 24-11-05 
      if (dateArr[0].length === 4) {
        year = dateArr[0];
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      }
      else if (dateArr[0].length === 2) { //ex. 20241-15
        year = setYearFormat(dateArr[0]);
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      }
      else if (dateArr[0].length === 5) {  //ex. 20241-5-, 20241-0-
        year = dateArr[0].substr(0, 4);
        month = dateArr[0].substr(4, 1)
        if (dateArr[1] > 2) {
          month = setMmddFormat(month)
        } else month = month;
        day = dateArr[1];
      }
      else {
        year = dateArr[0];
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      }
      return year + month + day;
    }
    else {
      return dateArr?.join('');
    }
  }
  else if (cntnt?.length === 7) {
    // Logger.log("2️⃣. 7자리 경우 2️⃣")
    if (dateArr.length === 1) { //ex. 2024105, 2024305, 2024015
      year = dateArr[0].substr(0, 4);
      let md = dateArr[0].substr(4,);
      if ((md.substr(0, 1) == 0)) { //ex.2024015 
        month = md.substr(0, 2);
        day = setMmddFormat(md.substr(2,));
      }
      else if ((md.substr(0, 1) == 1) && (md.substr(1, 1) < 3)) { //ex. 2024105 (1월인지 10월인지 모르기 때문에 그대로 추출)
        month = md;
      }
      else if ((md.substr(0, 1) > 1)) { //ex.2024305
        month = setMmddFormat(md.substr(0, 1));
        day = md.substr(1,);
      }
      return year + month + day;
    }
    else if (dateArr.length == 2) { // 오인식 (ex. 20241-05, 20241-5, 202411-05,202411-5...)
      if (dateArr[0].length == 2) { //ex. 24-0103
        year = setYearFormat(dateArr[0])
        if (dateArr[1].length == 4) {
          month = dateArr[1].substr(0, 2);
          day = dateArr[1].substr(2, 2);
        }
        else {
          resultDate = dateArr?.join('');
        }
        resultDate = year + month + day;
      }
      else if (dateArr[0]?.length === 4) { //ex.2024-15, 2401-15 구분이 명확하지 못함으로 그대로 추출
        year = dateArr[0].substr(0, 2)
        month = dateArr[0].substr(2, 2)
        day = dateArr[1]
        if ((month >= 1 && month <= 12)) { //가운데 두자리가 1~12일 경우만 YYMMDD
          year = setYearFormat(year);
          month = setMmddFormat(month);
          day = setMmddFormat(day);
        }
        else {
          if (day > 12) { //가운데 두자리가 12 초과 일 경우는 그대로 
            year = dateArr[0];
            month = setMmddFormat(day.substr(0, 1))
            day = setMmddFormat(day.substr(1,));
          }
        }
        resultDate = year + month + day;
      }
      else if (dateArr[0].length == 5) { //ex. 20241-2, 20241-5, 20243-6...
        year = dateArr[0].substr(0, 4);
        month = setMmddFormat(dateArr[0].substr(4,));
        day = setMmddFormat(dateArr[1].substr(0, 2));
        resultDate = year + month + day;
      }
      else resultDate = dateArr?.join('')
      return resultDate
    }
    else if (dateArr.length == 4) {
      if (dateArr[0].length == 2 && dateArr[3].length == 0)
        year = setYearFormat(dateArr[0])
      month = setMmddFormat(dateArr[1])
      day = setMmddFormat(dateArr[2])
      return year + month + day
    }
  }
  else if (cntnt?.length === 6) {
    // Logger.log("3️⃣. 6자리 경우 3️⃣")
    if (dateArr.length === 1) { //ex. 240103,202411 -가운데 두자리가 1~12일 경우만 YYMMDD, 이외는 그대로 추출
      year = cntnt.substr(0, 2)
      month = cntnt.substr(2, 2)
      day = cntnt.substr(4, 2)
      if ((month >= 1 && month <= 12)) {
        year = setYearFormat(year);
        month = setMmddFormat(month);
        day = setMmddFormat(day);
      }
      return year + month + day;
    }
    else if (dateArr.length === 2) {
      if (dateArr[0].length === 2) { //ex.24-115, 24-015, 24-615...
        year = setYearFormat(dateArr[0])
        if (dateArr[1].charAt(0) == 0) { //ex. 24-015
          month = dateArr[1].substr(0, 2);
          day = setMmddFormat(dateArr[1].substr(2,));
        }
        else if (dateArr[1].charAt(0) == 1) {
          month = dateArr[1];
        }
        else {
          month = setMmddFormat(dateArr[1].substr(0, 1));
          day = dateArr[1].substr(1,);
        }
      }
      else if (dateArr[0].length === 4) { //ex. 2024-3,  2401-5
        year = dateArr[0].substr(0, 2);
        month = dateArr[0].substr(2, 2)
        day = setMmddFormat(dateArr[1])
        if ((month >= 1 && month <= 12)) { //2401-5
          year = setYearFormat(year);
          month = setMmddFormat(month);
        } else { //2024-3
          year = dateArr[0];
          month = setMmddFormat(dateArr[1])
          day = ''
        }
      }
      else { //ex. 241-15, 20241-
        year = dateArr?.join('');
        month = '';
        day = '';
      }
      resultDate = year + month + day;
      return resultDate
    }
    else if (dateArr.length === 3) {
      if (dateArr[0].length == 2) { //ex. 24-1-1, 24-51-, 24--51
        year = setYearFormat(dateArr[0]);
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      }
      else { //ex. 2024--
        year = dateArr?.join('');
        month = '';
        day = '';
      }
      resultDate = year + month + day;
      return resultDate
    }
  }
  else if (cntnt?.length == 12) {
    if (dateArr.length == 5) {
      return dateArr.join('')
    }
    if (dateArr.length == 4 && dateArr[0].length == 5 && dateArr[3].length == "") {
      dateArr[0] = dateArr[0].slice(0, 4)
      return dateArr.join('')
    }
  }
  else if (cntnt?.length === 13) {
    // Logger.log(" 13자리 경우 ")
    if (dateArr.length == 2) {
      if (dateArr[0].length == 6) {
        year = cntnt.substr(0, 2)
        month = cntnt.substr(2, 2)
        day = cntnt.substr(4, 2)
        if ((month >= 1 && month <= 12)) {
          year = setYearFormat(year);
          month = setMmddFormat(month);
          day = setMmddFormat(day);
        }
        dateArr[0] = year + month + day
      }
      if (dateArr[1].length == 6) {
        year = cntnt.substr(0, 2)
        month = cntnt.substr(2, 2)
        day = cntnt.substr(4, 2)
        if ((month >= 1 && month <= 12)) {
          year = setYearFormat(year);
          month = setMmddFormat(month);
          day = setMmddFormat(day);
        }
        dateArr[1] = year + month + day
      }
    }
    if (dateArr.length == 3) {
      if (dateArr[2].length > 2) {
        dateArr[2] = dateArr[2].slice(0, 2)
      }
    }
    if (dateArr.length == 4) {
      if (dateArr[0].length == 4) {
        year = dateArr[0]
        month = dateArr[1]
        day = dateArr[2]
        dateArr = []
        dateArr[0] = year + month + day
      }
    }

    return dateArr.join('')
  }
  else if (cntnt?.length == 16) {
    // Logger.log(" 16자리 경우 ")
    if (dateArr.length == 1) {
      return dateArr.join('');
    }
    else if (dateArr.length == 5 && dateArr[2].length == 4) { //22.02.11~22.02.24
      resultDate = setYearFormat(dateArr[0]) + setMmddFormat(dateArr[1]) + setMmddFormat(dateArr[2].substr(0, 2))
      resultDate = resultDate + setYearFormat(dateArr[2].substr(2, 4)) + setMmddFormat(dateArr[3]) + setMmddFormat(dateArr[4]);
      return resultDate;
    }
    else return dateArr.join('').substr(0, 16);
  }
  else if (cntnt?.length === 17) {
    if (dateArr.length == 2) {
      return dateArr.join('').substr(0, 16);
    }
    else if (dateArr.length == 6) { //22.02.12-22.02.24
      resultDate = setYearFormat(dateArr[0]) + setMmddFormat(dateArr[1]) + setMmddFormat(dateArr[2])
      resultDate = resultDate + setYearFormat(dateArr[3]) + setMmddFormat(dateArr[4]) + setMmddFormat(dateArr[5]);
      return resultDate;
    }
    else return dateArr.join('');
  }
  else if (cntnt !== undefined && cntnt?.length === 20) {

  }
  // else if(cntnt?.length==20){
  //   // if(dateArr.length==6){
  //   //   resultDate = setYearFormat(dateArr[0])+ setMmddFormat(dateArr[1])+setMmddFormat(dateArr[2])
  //   //   resultDate= resultDate+ setYearFormat(dateArr[3])+ setMmddFormat(dateArr[4])+setMmddFormat(dateArr[5]);
  //   // }else return dateArr.join('');
  // }
  else { //2021-08-10~2021-08-10, 그외..
    Logger.log('🚨🚨🚨🚨🚨🚨🚨 날짜 포멧'+ cntnt);
    return dateArr.join('');
  }
}

//날짜 포멧 YYYYMMDD 통일
exports.setDateYYYYMMDD = function setDateYYYYMMDD(input) {
  if (!input) return "";

  let str = String(input).trim();

  // 1️⃣ 한글 제거 및 구분자 통일
  str = str
    .replace(/년|월/g, "-")
    .replace(/일/g, "")
    .replace(/[./]/g, "-");
  // 2️⃣ YYYY-MM-DD or YY-MM-DD
  let match = str.match(/^(\d{2,4})-(\d{1,2})-(\d{1,2})$/);
  if (match) {
    let year = match[1];
    let month = match[2];
    let day = match[3];

    if (year.length === 2) {
      year = Number(year) >= 50 ? `19${year}` : `20${year}`;
    }

    return (
      year +
      month.padStart(2, "0") +
      day.padStart(2, "0")
    );
  }

  // 3️⃣ YYYYMMDD
  if (/^\d{8}$/.test(str)) {
    return str;
  }

  // 4️⃣ YYMMDD
  if (/^\d{6}$/.test(str)) {
    const yy = str.slice(0, 2);
    const rest = str.slice(2);
    const year = Number(yy) >= 50 ? `19${yy}` : `20${yy}`;
    return year + rest;
  }

  if (/^\d{1,5}$/.test(str)) {
    return input;
  }

  // ❌ 인식 불가
  return "";
}


/**
 * 2024.09.23 루나
 * @param {*} year  
 * @returns 
 */
function setYearFormat(year) {
  let cntntYear = year.substr(0, 2);  // 앞의 두 자리를 연도로 추출
  let monthDay = year.substr(2);      // 나머지 부분은 월과 일로 처리

  // 현재 연도의 마지막 두 자리를 추출
  let currentYear = String(new Date().getFullYear()).substr(2, 2);

  let fullYear = cntntYear <= currentYear ? '20' + cntntYear : '19' + cntntYear;

  return fullYear;
}

/**
 * 2024.09.23 루나
 * @param {*} date 
 * @returns 
 */
function setMmddFormat(date) {
  return date?.length === 1 ? '0' + date : date;
}

function resultFormat(keyObj, extrtId, lvlNo, extrtSno, uppExtrtItmNm, extrtItmNm, extrtRawItmNm, extrtCntnt, itmValCoordVal, itmNmCoordVal, selfRlbtyVal, extrtYn, chartNm, acd_ogtdt) {

  if (Object.keys(keyObj).length < 1) keyObj = { "추출항목": [], "표타이틀": [], "표추출항목": [], "표레이블": [] };

  if (typeof selfRlbtyVal !== 'number') selfRlbtyVal = parseFloat(selfRlbtyVal);
  if (isNaN(selfRlbtyVal)) selfRlbtyVal = 0;

  if (typeof extrtCntnt === 'undefined' || extrtCntnt === 'undefined') extrtCntnt = '';

  let result = {
    img_extc_itnm: extrtItmNm                                       // (String) 추출항목명
    , lvl_no: lvlNo || 1                                       // (int) 추출레벨번호
    , extc_itm_no: extrtId                                                // (int) 추출ID - for문 돌릴 때 1부터 +1 증가 (추출 순서)
    , extc_rst_seq: extrtSno || 0                                       // (int) 추출일련번호
    , hgrk_extc_itm_no: 0
    , extc_itm_tpvl: ''
    // , upp_extrtItmNm : uppExtrtItmNm                                // (String) 상위추출항목명 ex) 본인부담금, 공단부담금, ...
    // , extrt_raw_itm_nm : extrtRawItmNm                                // (String) 추출원본항목명 (detectedLabel)
    , extc_rst_cont01: extrtCntnt || ''                                  // (String) 추출내용
    , extc_rst_cont09: ''
    , extc_rst_cont10: chartNm                                               // (String) 표데이터 표 이름
    , self_rlbtr_vl: Math.floor(selfRlbtyVal * 100) / 100 || 1.00   // (float) 본인신뢰도값
    , extc_rst_img_crdn_vl: itmValCoordVal || []                        // (String) 항목값좌표값
    // , extc_rst_img_crdn_vl: itmNmCoordVal || []                          // (String) 항목명좌표값
    , extrtYn: extrtYn || "N"                                 // (String) 추출여부 - 이미지에서 추출 됐으면 Y, 없으면 
    , acd_ogtdt: acd_ogtdt || ''                             //사고발생일자
  };

  return result;
}

function getYTopBottom(coords) {
  const ys = [coords[1], coords[3], coords[5], coords[7]];
  return { top: Math.min(...ys), bottom: Math.max(...ys) };
}

function filterArrtcdNearLastRowBottomY(
  arrtcd,
  lastRowBottomY,
  lastRowFirstX,
  yTol = 5,
  xLeftTol = 10,
  xRightTol = 500
) {
  if (!Array.isArray(arrtcd)) return [];
  if (!Number.isFinite(lastRowBottomY) || !Number.isFinite(lastRowFirstX)) return [];

  return arrtcd
    .map(item => {
      const coord = item?.coord;
      if (!Array.isArray(coord) || coord.length < 8) return null;

      // topY = coord 중 가장 위 y
      const ys = [coord[1], coord[3], coord[5], coord[7]].filter(Number.isFinite);
      if (ys.length === 0) return null;
      const topY = Math.min(...ys);

      // leftX = coord 중 가장 왼쪽 x
      const xs = [coord[0], coord[2], coord[4], coord[6]].filter(Number.isFinite);
      if (xs.length === 0) return null;
      const leftX = Math.min(...xs);

      // ✅ Y 조건
      if (Math.abs(topY - lastRowBottomY) > yTol) return null;

      // ✅ X 조건
      if (leftX < lastRowFirstX - xLeftTol) return null;
      if (leftX > lastRowFirstX + xRightTol) return null;

      return {
        ...item,
        _topY: topY,
        _leftX: leftX
      };
    })
    .filter(Boolean);
}
function mergeNearTexts(near) {
  if (!Array.isArray(near)) return "";

  return near
    .slice()
    .sort((a, b) => (a._leftX ?? 0) - (b._leftX ?? 0)) // 왼→오
    .map(v => v.mergetext ?? "")
    .join("");
}

function getTopY(item) {
  const c = item?.coord;
  if (!Array.isArray(c) || c.length < 8) return null;
  const ys = [c[1], c[3], c[5], c[7]].filter(Number.isFinite);
  return ys.length ? Math.min(...ys) : null;
}

function getLeftX(item) {
  const c = item?.coord;
  if (!Array.isArray(c) || c.length < 8) return null;
  const xs = [c[0], c[2], c[4], c[6]].filter(Number.isFinite);
  return xs.length ? Math.min(...xs) : null;
}

function expandDiagnosisByNearLines({
  rowTexts,
  arrtcd,
  startBottomY,
  startFirstX,
  yTol = 5,
  xLeftTol = 10,
  xRightTol = 500,
  maxSteps = 10,            // 안전장치
  rowGap = 8                // rows 그룹핑에 쓰던 값과 맞추면 좋음
}) {
  let lastBottomY = startBottomY;
  let lastFirstX = startFirstX;

  const used = new Set();   // arrtcd index(또는 배열 index) 중복 방지

  for (let step = 0; step < maxSteps; step++) {
    // 1) near 후보 찾기 (기존 함수 사용)
    let near = filterArrtcdNearLastRowBottomY(
      arrtcd,
      lastBottomY,
      lastFirstX,
      yTol,
      xLeftTol,
      xRightTol
    );

    // 2) 이미 사용한 arrtcd 제거(중복 방지)
    near = (near ?? []).filter(n => {
      const id = n?.index ?? n?._index ?? null; // 너 데이터에 index 있음
      if (id === null) return true;
      if (used.has(id)) return false;
      return true;
    });

    if (!near || near.length === 0) break;

    // 3) 이번 near는 이제 사용 처리
    near.forEach(n => {
      const id = n?.index ?? n?._index ?? null;
      if (id !== null) used.add(id);
    });

    // 4) 텍스트 머지
    const merged = mergeNearTexts(near);
    if (!merged) break;

    const mergedClean = String(merged).trim();
    const isNewLineStart =
      /^[\[(](?:부|주)/.test(mergedClean) || /^\[부\]/.test(mergedClean);

    if (isNewLineStart) {
      rowTexts.push(mergedClean);
    } else {
      rowTexts[rowTexts.length - 1] = (rowTexts[rowTexts.length - 1] + " " + mergedClean).trim();
    }

    // 5) ✅ 다음 반복을 위해 lastBottomY / lastFirstX 갱신
    //    - lastBottomY: 이번 near 라인의 "bottomY" (arrtcd는 topY 기준으로 잡았으니 bottom은 coord max y로 계산)
    //    - lastFirstX: 이번 near 라인의 leftX 최솟값
    const nearBottomY = Math.max(
      ...near.map(n => {
        const c = n?.coord;
        if (!Array.isArray(c) || c.length < 8) return 0;
        const ys = [c[1], c[3], c[5], c[7]].filter(Number.isFinite);
        return ys.length ? Math.max(...ys) : 0;
      })
    );

    const nearFirstX = Math.min(
      ...near.map(n => {
        const lx = n?._leftX ?? getLeftX(n);
        return Number.isFinite(lx) ? lx : Infinity;
      })
    );

    // 갱신 실패하면 중단
    if (!Number.isFinite(nearBottomY) || nearBottomY <= 0) break;
    if (!Number.isFinite(nearFirstX) || nearFirstX === Infinity) break;

    lastBottomY = nearBottomY;
    lastFirstX = nearFirstX;
  }

  return rowTexts;
}

//사고발생일자
function pickAccidentDate(values) {
  const getItem = (name) => values.find(v => v?.img_extc_itnm === name);

  //YYYYMMDD만 검증
  const normalizeYYYYMMDD = (s) => {
    const raw = String(s ?? "").trim();
    if (!raw) return "";
    const m = raw.match(/(\d{4})(\d{2})(\d{2})/);
    if (!m) return "";
    const y = Number(m[1]), mo = Number(m[2]), d = Number(m[3]);

    if (y < 1900 || y > 2100) return "";
    if (mo < 1 || mo > 12) return "";
    if (d < 1 || d > 31) return "";
    return `${m[1]}${m[2]}${m[3]}`;
  };

  const candidates = [
    normalizeYYYYMMDD(getItem("진단일")?.extc_rst_cont01),
    normalizeYYYYMMDD(getItem("수술일자")?.extc_rst_cont01),
    normalizeYYYYMMDD(getItem("검사일")?.extc_rst_cont01),
    normalizeYYYYMMDD(getItem("치료일")?.extc_rst_cont01),
  ].filter(Boolean);

  if (candidates.length === 0) return "";

  //YYYYMMDD 날짜 오름차순
  candidates.sort();
  return candidates[0];
}

exports.fillAccidentDate = function fillAccidentDate(values) {
  // const accidentItem = values.find(v=>v?.img_extc_itnm==="사고발생일자");
  // if(!accidentItem) return values;

  const picked = pickAccidentDate(values);
  // accidentItem.extc_rst_cont01 = picked;
  // return values; //하나의 객체로 넣을때 사용
  return picked // 항목별 컬럼추가로 사용
}

//주민번호 뒷자리 7자리 이상일때 자르기
exports.idNumPattern = function idNumPattern(data) {
  let s = data;
  if (!s.includes("-")) {
    if (s.includes(".")) {
      s = s.replace(".", "-")
    }
    else {
      s = s.replace(/^(\d{6})/, "$1-")
    }
  }

  const [front, backRaw = ""] = s.split("-", 2);
  const backDigits = backRaw.replace(/\D/g, "");

  const back7 = backDigits.length > 7 ? backDigits.slice(0, 7) : backDigits;

  return `${front}-${back7}`

}
